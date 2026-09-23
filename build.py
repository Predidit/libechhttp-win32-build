#!/usr/bin/env python3
"""Build the pinned dependency SDK. No ech_http application code is needed."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tarfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent


def run(args, **kwargs):
    print('+', ' '.join(map(str, args)), flush=True)
    subprocess.run(list(map(str, args)), check=True, **kwargs)


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def sources(manifest, cache):
    cache.mkdir(parents=True, exist_ok=True)
    revision = manifest['boringssl']['revision']
    boring = cache / f'boringssl-{revision}'
    if not (boring / '.git').exists():
        run(['git', 'init', boring])
        run(['git', '-C', boring, 'remote', 'add', 'origin', manifest['boringssl']['repository']])
        run(['git', '-C', boring, 'fetch', '--depth=1', 'origin', revision])
        run(['git', '-c', 'core.longpaths=true', '-C', boring, 'checkout', '--detach', revision])
    actual = subprocess.check_output(['git', '-C', str(boring), 'rev-parse', 'HEAD'], text=True).strip()
    if actual != revision:
        raise RuntimeError('BoringSSL revision mismatch')
    curl = manifest['curl']
    archive = cache / f"curl-{curl['version']}.tar.xz"
    if not archive.exists() or digest(archive) != curl['sha256']:
        with urllib.request.urlopen(curl['url'], timeout=120) as source, archive.open('wb') as output:
            shutil.copyfileobj(source, output)
    if digest(archive) != curl['sha256']:
        raise RuntimeError('curl SHA-256 mismatch')
    curl_dir = cache / f"curl-{curl['version']}"
    if not curl_dir.exists():
        with tarfile.open(archive) as tar:
            tar.extractall(cache, filter='data')
    return boring, curl_dir


def toolchain(target, work):
    env = dict(os.environ)
    args = []
    if target.startswith('windows-'):
        if platform.system() != 'Windows':
            raise RuntimeError('Windows builds require MSVC on Windows')
        vswhere = Path(env['ProgramFiles(x86)']) / 'Microsoft Visual Studio/Installer/vswhere.exe'
        vs = Path(subprocess.check_output([str(vswhere), '-latest', '-products', '*', '-requires',
                                          'Microsoft.VisualStudio.Component.VC.Tools.x86.x64',
                                          '-property', 'installationPath'], text=True).strip())
        arch = {'x64': 'x64', 'arm64': 'arm64', 'ia32': 'x86'}[target.split('-')[1]]
        capture = work / 'environment.cmd'
        capture.write_text(f'@echo off\ncall "{vs}/Common7/Tools/VsDevCmd.bat" -no_logo -host_arch=x64 -arch={arch} >nul\nif errorlevel 1 exit /b 1\nset\n')
        text = subprocess.check_output([env.get('COMSPEC', 'cmd.exe'), '/d', '/c', str(capture)], text=True)
        env = {key.upper(): value for key, value in
               (line.split('=', 1) for line in text.splitlines() if '=' in line and not line.startswith('='))}
        cmake_dir = vs / 'Common7/IDE/CommonExtensions/Microsoft/CMake'
        env['PATH'] = f"{cmake_dir / 'CMake/bin'};{cmake_dir / 'Ninja'};{env.get('Path', env.get('PATH', ''))}"
        args += ['-DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreaded']
    elif target.startswith('android-'):
        ndk = Path(env['ANDROID_NDK_HOME'])
        props = (ndk / 'source.properties').read_text()
        if '28.2.13676358' not in props:
            raise RuntimeError('Release builds require Android NDK 28.2.13676358')
        abi = {'arm': 'armeabi-v7a', 'arm64': 'arm64-v8a', 'ia32': 'x86', 'x64': 'x86_64'}[target.split('-')[1]]
        args += [f'-DCMAKE_TOOLCHAIN_FILE={ndk}/build/cmake/android.toolchain.cmake',
                 f'-DANDROID_ABI={abi}', '-DANDROID_PLATFORM=android-21', '-DANDROID_STL=c++_static']
    elif target.startswith(('macos-', 'ios-')):
        if platform.system() != 'Darwin':
            raise RuntimeError('Apple builds require Xcode on macOS')
        arch = 'arm64' if '-arm64' in target else 'x86_64'
        args += [f'-DCMAKE_OSX_ARCHITECTURES={arch}']
        if target.startswith('ios-'):
            sdk = 'iphonesimulator' if target.endswith('-simulator') else 'iphoneos'
            args += ['-DCMAKE_SYSTEM_NAME=iOS', '-DCMAKE_MACOSX_BUNDLE=OFF',
                     f'-DCMAKE_OSX_SYSROOT={sdk}', '-DCMAKE_OSX_DEPLOYMENT_TARGET=13.0']
        else:
            args += ['-DCMAKE_OSX_DEPLOYMENT_TARGET=' + ('11.0' if arch == 'arm64' else '10.15')]
    elif target.startswith('linux-'):
        machine = {'x86_64': 'x64', 'aarch64': 'arm64'}.get(platform.machine())
        if platform.system() != 'Linux' or target != f'linux-{machine}':
            raise RuntimeError('Linux dependency builds require the matching host architecture')
        args += ['-DCMAKE_C_COMPILER=gcc-11', '-DCMAKE_CXX_COMPILER=g++-11']
    else:
        raise ValueError(target)
    return env, args


def main():
    manifest = json.loads((ROOT / 'dependencies.json').read_text())
    parser = argparse.ArgumentParser()
    parser.add_argument('--target', choices=manifest['targets'], required=True)
    parser.add_argument('--source-cache', type=Path, default=ROOT / 'build/sources')
    options = parser.parse_args()
    target = options.target
    work = ROOT / 'build' / target
    work.mkdir(parents=True, exist_ok=True)
    env, arguments = toolchain(target, work)
    cmake = shutil.which('cmake', path=env.get('PATH', env.get('Path')))
    ninja = shutil.which('ninja', path=env.get('PATH', env.get('Path')))
    if not cmake or not ninja:
        raise RuntimeError('Install CMake >=3.22 and Ninja')
    boring, curl = sources(manifest, options.source_cache.resolve())
    common = ['-G', 'Ninja', f'-DCMAKE_MAKE_PROGRAM={ninja}', '-DCMAKE_BUILD_TYPE=Release',
              '-DCMAKE_POSITION_INDEPENDENT_CODE=ON', '-DCMAKE_C_VISIBILITY_PRESET=hidden',
              '-DCMAKE_CXX_VISIBILITY_PRESET=hidden', '-DCMAKE_VISIBILITY_INLINES_HIDDEN=ON', *arguments]
    parallel = str(min(os.cpu_count() or 2, 8))
    boring_build = work / 'boringssl'
    run([cmake, '-S', boring, '-B', boring_build, *common, '-DBUILD_SHARED_LIBS=OFF',
         '-DBUILD_TESTING=OFF', '-DOPENSSL_NO_ASM=ON', '-DOPENSSL_SMALL=ON'], env=env)
    run([cmake, '--build', boring_build, '--target', 'ssl', 'crypto', '--parallel', parallel], env=env)
    curl_build = work / 'curl'
    run([cmake, '-S', ROOT / 'cmake', '-B', curl_build, *common,
         f'-DEH_CURL_SOURCE={curl}', f'-DEH_BORINGSSL_SOURCE={boring}',
         f'-DEH_BORINGSSL_BUILD={boring_build}'], env=env)
    run([cmake, '--build', curl_build, '--target', 'echhttp_deps_probe', '--parallel', parallel], env=env)
    cache_text = (curl_build / 'CMakeCache.txt').read_text()
    if 'HAVE_SSL_SET1_ECH_CONFIG_LIST:INTERNAL=1' not in cache_text:
        raise RuntimeError('libcurl was built without BoringSSL ECH support')
    # The probe also checks curl feature reporting at runtime on native hosts.
    native = ((target == 'windows-x64' and platform.machine().lower() in ('amd64', 'x86_64')) or
              target.startswith('linux-') or
              target == ('macos-arm64' if platform.machine() == 'arm64' else 'macos-x64'))
    if native:
        run([cmake, '--build', curl_build, '--target', 'echhttp_deps_check', '--parallel', parallel], env=env)
        run([curl_build / ('echhttp_deps_check.exe' if os.name == 'nt' else 'echhttp_deps_check')], env=env)
    stage = work / 'sdk'
    (stage / 'lib').mkdir(parents=True, exist_ok=True)
    shutil.copytree(boring / 'include/openssl', stage / 'include/openssl', dirs_exist_ok=True)
    shutil.copytree(curl / 'include/curl', stage / 'include/curl', dirs_exist_ok=True)
    windows = target.startswith('windows-')
    libraries = [(curl_build / 'curl/lib' / ('libcurl.lib' if windows else 'libcurl.a'),
                  'curl.lib' if windows else 'libcurl.a')]
    libraries += [(boring_build / (f'{name}.lib' if windows else f'lib{name}.a'),
                   f'{name}.lib' if windows else f'lib{name}.a') for name in ('ssl', 'crypto')]
    for source, filename in libraries:
        shutil.copyfile(source, stage / 'lib' / filename)
    shutil.copytree(ROOT / 'licenses', stage / 'licenses', dirs_exist_ok=True)
    (stage / 'cmake').mkdir(exist_ok=True)
    shutil.copyfile(ROOT / 'cmake/EchHttpDeps.cmake', stage / 'cmake/EchHttpDeps.cmake')
    metadata = {'schema': 1, 'release': manifest['release'], 'target': target,
                'curl': manifest['curl'], 'boringssl': manifest['boringssl'],
                'build_commit': os.environ.get('GITHUB_SHA', 'local'),
                'cmake': subprocess.check_output([cmake, '--version'], text=True, env=env).splitlines()[0],
                'compiler': next(line for line in cache_text.splitlines() if line.startswith('CMAKE_CXX_COMPILER:')),
                'android_ndk': '28.2.13676358' if target.startswith('android-') else None,
                'linux_baseline': 'glibc 2.35, GCC 11/libstdc++' if target.startswith('linux-') else None,
                'files': {p.relative_to(stage).as_posix(): digest(p) for p in sorted(stage.rglob('*'))
                          if p.is_file() and p.name != 'metadata.json'}}
    (stage / 'metadata.json').write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
    dist = ROOT / 'dist'
    dist.mkdir(exist_ok=True)
    archive = dist / f"libechhttp-deps-{manifest['release']}-{target}.zip"
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as output:
        for source in sorted(stage.rglob('*')):
            if source.is_file():
                info = zipfile.ZipInfo(source.relative_to(stage).as_posix(), date_time=(2026, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                output.writestr(info, source.read_bytes())
    archive.with_suffix('.zip.sha256').write_text(f'{digest(archive)}  {archive.name}\n')
    print(f'Packaged {archive.name}: {archive.stat().st_size} bytes', flush=True)


if __name__ == '__main__':
    main()

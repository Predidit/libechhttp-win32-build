import argparse
import hashlib
import json
from pathlib import Path
import zipfile

parser = argparse.ArgumentParser(description='Verify a complete dependency SDK release')
parser.add_argument('tag')
parser.add_argument('--commit', help='Require this exact source commit in every archive')
args = parser.parse_args()

manifest = json.loads(Path('dependencies.json').read_text())
if args.tag != manifest['release']:
    raise SystemExit('Tag does not match the pinned manifest release')
dist = Path('dist')
checksums = []
for target in manifest['targets']:
    archive = dist / f"libechhttp-deps-{manifest['release']}-{target}.zip"
    expected = archive.with_suffix('.zip.sha256').read_text().split()[0]
    with archive.open('rb') as stream:
        actual = hashlib.file_digest(stream, 'sha256').hexdigest()
    if actual != expected:
        raise SystemExit(f'Checksum mismatch: {target}')
    with zipfile.ZipFile(archive) as sdk:
        metadata = json.loads(sdk.read('metadata.json'))
        if args.commit and metadata.get('build_commit') != args.commit:
            raise SystemExit(f'Source commit mismatch: {target}')
        if metadata['target'] != target or metadata['release'] != manifest['release']:
            raise SystemExit(f'Metadata mismatch: {target}')
        if any(metadata.get(name) != manifest[name] for name in ('curl', 'boringssl', 'zlib')):
            raise SystemExit(f'Dependency pin mismatch: {target}')
        extension, prefix = ('lib', '') if target.startswith('windows-') else ('a', 'lib')
        required = {'include/zlib.h', 'include/zconf.h', 'licenses/ZLIB_LICENSE',
                    f'lib/{prefix}zlib.{extension}'}
        if not required.issubset(metadata['files']):
            raise SystemExit(f'Incomplete zlib SDK: {target}')
        for path, checksum in metadata['files'].items():
            if hashlib.sha256(sdk.read(path)).hexdigest() != checksum:
                raise SystemExit(f'File checksum mismatch: {path}')
    checksums.append(f'{actual}  {archive.name}')
(dist / 'SHA256SUMS').write_text('\n'.join(checksums) + '\n')
print(f'Verified {len(checksums)} SDK archives')

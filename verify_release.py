import hashlib
import json
from pathlib import Path
import sys
import zipfile

manifest = json.loads(Path('dependencies.json').read_text())
if sys.argv[1] != manifest['release']:
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
        if metadata['target'] != target or metadata['release'] != manifest['release']:
            raise SystemExit(f'Metadata mismatch: {target}')
        for path, checksum in metadata['files'].items():
            if hashlib.sha256(sdk.read(path)).hexdigest() != checksum:
                raise SystemExit(f'File checksum mismatch: {path}')
    checksums.append(f'{actual}  {archive.name}')
(dist / 'SHA256SUMS').write_text('\n'.join(checksums) + '\n')
print(f'Verified {len(checksums)} SDK archives')

import argparse
import base64
import gzip
import hashlib
import io
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tarfile

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / ".github/publishing.bin"
MAGIC = b"PRESENCE\x01"
LIMIT = 16 * 1024 * 1024
DIRECTORIES = {"scripts", "tests", "docs"}


def cipher():
    key = base64.b64decode(os.environ["PUBLISHING_KEY"].strip(), validate=True)
    if len(key) != 32:
        raise ValueError("Invalid publishing key")
    return AESGCM(key)


def encrypt(data):
    digest = hashlib.sha256(data).digest()
    prefix = MAGIC + digest
    nonce = os.urandom(12)
    return prefix + nonce + cipher().encrypt(nonce, data, prefix)


def decrypt(data):
    offset = len(MAGIC) + 32
    if not data.startswith(MAGIC) or len(data) < offset + 28:
        raise ValueError("Invalid publishing package")
    plain = cipher().decrypt(data[offset:offset + 12], data[offset + 12:], data[:offset])
    if len(plain) > LIMIT or hashlib.sha256(plain).digest() != data[len(MAGIC):offset]:
        raise ValueError("Invalid publishing package")
    return plain


def restore():
    plain = decrypt(BUNDLE.read_bytes())
    entries = []
    names = set()
    total = 0
    with tarfile.open(fileobj=io.BytesIO(plain), mode="r:gz") as archive:
        for member in archive:
            path = PurePosixPath(member.name)
            total += member.size
            if not member.isfile() or path.is_absolute() or ".." in path.parts or not path.parts or path.parts[0] not in DIRECTORIES or member.name in names or member.size < 0 or total > LIMIT:
                raise ValueError("Invalid publishing package entry")
            destination = ROOT.joinpath(*path.parts)
            if destination.resolve() != destination or destination.is_symlink():
                raise ValueError("Unsafe publishing package path")
            names.add(member.name)
            entries.append((destination, archive.extractfile(member).read()))
    if not entries or "scripts/service_tasks.py" not in names:
        raise ValueError("Incomplete publishing package")
    for destination, content in entries:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        destination.chmod(0o600)
    if os.environ.get("GITHUB_OUTPUT"):
        subprocess.run([sys.executable, str(ROOT / "scripts/service_tasks.py"), "configure"], cwd=ROOT, check=True)


def seal():
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w", format=tarfile.PAX_FORMAT) as archive:
        for directory in sorted(DIRECTORIES):
            for path in sorted((ROOT / directory).rglob("*")):
                if path.is_symlink():
                    raise ValueError("Publishing package cannot contain links")
                if not path.is_file() or "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
                    continue
                content = path.read_bytes()
                info = tarfile.TarInfo(path.relative_to(ROOT).as_posix())
                info.size = len(content)
                info.mode = 0o600
                archive.addfile(info, io.BytesIO(content))
    if output.tell() > LIMIT:
        raise ValueError("Publishing package is too large")
    plain = gzip.compress(output.getvalue(), mtime=0)
    if BUNDLE.exists() and decrypt(BUNDLE.read_bytes()) == plain:
        return
    temporary = BUNDLE.with_suffix(".pending")
    temporary.write_bytes(encrypt(plain))
    temporary.replace(BUNDLE)


def run(task, arguments):
    if not task.replace("-", "").isalnum():
        raise ValueError("Invalid publishing task")
    temporary = Path(os.environ.get("RUNNER_TEMP", "/tmp")) / "presence-diagnostics"
    temporary.mkdir(mode=0o700, parents=True, exist_ok=True)
    log = temporary / (task + ".log")
    log.touch(mode=0o600, exist_ok=True)
    try:
        with log.open("wb") as output:
            result = subprocess.run([sys.executable, str(ROOT / "scripts/service_tasks.py"), task, *arguments], cwd=ROOT, stdout=output, stderr=subprocess.STDOUT)
        if result.returncode or task == "sample":
            diagnostic = encrypt(log.read_bytes()[-LIMIT:])
            (temporary / (task + ".bin")).write_bytes(diagnostic)
            message = base64.b64encode(encrypt(log.read_bytes()[-12000:])).decode()
            parts = [message[index:index + 2800] for index in range(0, len(message), 2800)]
            for index, part in enumerate(parts, 1):
                print(f"::notice title=Private diagnostic {index}/{len(parts)}::" + part, flush=True)
        if result.returncode:
            print(f"::error title=Publication check::{task} failed; encrypted diagnostics retained.", flush=True)
        else:
            print(f"Publication task {task} completed.", flush=True)
        return result.returncode
    finally:
        log.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=["restore", "seal", "run"])
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.operation == "run":
        if not args.arguments:
            raise ValueError("Publishing task is required")
        return run(args.arguments[0], args.arguments[1:])
    if args.arguments:
        raise ValueError("Unexpected publishing arguments")
    globals()[args.operation]()
    print(f"Publishing package {args.operation} completed.", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"::error title=Publishing service::The publishing service could not complete the requested operation ({type(error).__name__}).", flush=True)
        raise SystemExit(1)

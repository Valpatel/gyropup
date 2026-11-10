"""Import-safe read-only identity of the retained native runtime and toolkit."""
from pathlib import Path
import hashlib
import json
import stat


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def tree(root):
    root=Path(root).resolve();out={};cache={}
    def hashed(path):
        key=path.resolve()
        if key not in cache:cache[key]=digest(key)
        return cache[key]
    for path in sorted(root.rglob('*')):
        st=path.lstat();key=path.relative_to(root).as_posix()
        if stat.S_ISDIR(st.st_mode):continue
        if stat.S_ISREG(st.st_mode):out[key]={'kind':'file','mode':stat.S_IMODE(st.st_mode),'bytes':st.st_size,'sha256':hashed(path)}
        elif stat.S_ISLNK(st.st_mode):
            target=path.resolve(strict=True)
            if target.is_dir():
                if not target.is_relative_to(root):raise ValueError('Runtime has external directory alias')
                out[key]={'kind':'directory-link','target':target.relative_to(root).as_posix()}
            elif target.is_file():out[key]={'kind':'file-link','target_identity':hashlib.sha256(str(target).encode()).hexdigest(),'sha256':hashed(target)}
            else:raise ValueError('Unsupported runtime link')
        else:raise ValueError('Nonregular runtime entry')
    return out


def fingerprint(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()

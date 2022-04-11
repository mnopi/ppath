# coding=utf-8
"""
Ppath package
"""
__all__ = (
    "MACOS",
    "EnumLower",
    "PIs",
    "Path",
    "Passwd",
    "PathStat",
    "toiter",
    "which",
)

import collections
import contextlib
import enum
import grp
import hashlib
import os
import pathlib
import platform
import pwd
import shutil
import stat
import subprocess
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass
from dataclasses import field
from typing import Union

MACOS = platform.system == "Darwin"
"""True if :func:`platform.system` is Darwin."""

_cache_passwd = {}
_cache_which = {}


class CalledProcessError(subprocess.SubprocessError):
    """
    Patched :class:`subprocess.CalledProcessError`.

    Raised when run() and the process returns a non-zero exit status.

    Attributes:
        cmd: The command that was run.
        returncode: The exit code of the process.
        output: The output of the process.
        stderr: The error output of the process.
        process: :class:`subprocess.CompletedProcess` object.
    """
    def __init__(self, returncode, cmd, output=None, stderr=None, process=None):
        self.returncode = returncode
        self.cmd = cmd
        self.output = output
        self.stderr = stderr
        self.process = process

    def __str__(self):
        value = super().__str__()
        if self.stderr is not None:
            value += "\n" + self.stderr
        elif self.process is not None and self.process.stderr is not None:
            value += "\n" + self.process.stderr
        if self.stdout is not None:
            value += "\n" + self.stdout
        elif self.process is not None and self.process.stdout is not None:
            value += "\n" + self.process.stdout
        return value

    @property
    def stdout(self):
        """Alias for output attribute, to match stderr"""
        return self.output

    @stdout.setter
    def stdout(self, value):
        # There's no obvious reason to set this, but allow it anyway so
        # .stdout is a transparent alias for .output
        self.output = value


subprocess.CalledProcessError = CalledProcessError


class EnumLower(enum.Enum):
    def _generate_next_value_(self, start, count, last_values):
        return self.lower()


class PIs(EnumLower):
    """Path Is Dir or File Enum Class."""
    EXISTS = enum.auto()
    IS_DIR = enum.auto()
    IS_FILE = enum.auto()


class Path(pathlib.Path, pathlib.PurePosixPath):

    def __call__(self, name='', file=PIs.IS_DIR, passwd=None, mode=None):
        """
        Make dir or touch file and create subdirectories as needed.

        Examples:
            >>> with Path.tempdir() as t:
            ...     p = t('1/2/3/4')
            ...     assert p.is_dir() is True
            ...     p = t('1/2/3/4/5/6/7.py', file=PIs.IS_FILE)
            ...     assert p.is_file() is True
            ...     t('1/2/3/4/5/6/7.py/8/9.py', file=PIs.IS_FILE) # doctest: +IGNORE_EXCEPTION_DETAIL, +ELLIPSIS
            Traceback (most recent call last):
            NotADirectoryError

        Args:
            name: path to add.
            file: file or directory.
            passwd: user.
            mode: mode.

        Returns:
            Path.
        """
        # noinspection PyArgumentList
        return (self.mkdir if file is PIs.IS_DIR or file is PIs.EXISTS else self.touch)(
            name=name, passwd=passwd, mode=mode
        )

    def __contains__(self, value):
        """
        Checks all items in value exist in self.resolve().

        To check only parts use self.has.

        Examples:
            >>> assert '/usr' in Path('/usr/local')
            >>> assert 'usr local' in Path('/usr/local')
            >>> assert 'home' not in Path('/usr/local')
            >>> assert '' not in Path('/usr/local')
            >>> assert '/' in Path()
            >>> assert os.environ["USER"] in Path.home()

        Args:
            value: space separated list of items to check, or iterable of items.

        Returns:
            bool
        """
        value = Path(value) if isinstance(value, str) and "/" in value else toiter(value)
        return all([item in self.resolve().parts for item in value])

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return NotImplemented
        return self._cparts == other._cparts

    def __hash__(self):
        return self._hash if hasattr(self, '_hash') else hash(tuple(self._cparts))

    def __iter__(self):
        """
        Iterate over path parts.

        Examples:
            >>> assert list(Path('/usr/local')) == ['/', 'usr', 'local',]

        Returns:
            Iterable of path parts.
        """
        return iter(self.parts)

    def __lt__(self, other):
        if not isinstance(other, self.__class__):
            return NotImplemented
        return self._cparts < other._cparts

    def __le__(self, other):
        if not isinstance(other, self.__class__):
            return NotImplemented
        return self._cparts <= other._cparts

    def __gt__(self, other):
        if not isinstance(other, self.__class__):
            return NotImplemented
        return self._cparts > other._cparts

    def __ge__(self, other):
        if not isinstance(other, self.__class__):
            return NotImplemented
        return self._cparts >= other._cparts

    def _is_file(self):
        """Find up to the first directory in the path and check if it is a file."""
        p = self.resolve()
        while True:
            if p.is_file():
                return p.text
            elif p.is_dir() or (p := p.parent.resolve()) == Path('/'):
                return None

    def access(self, os_mode=os.W_OK, *, dir_fd=None, effective_ids=False, follow_symlinks=True):
        # noinspection LongLine
        """
        Use the real uid/gid to test for access to a path `Real Effective IDs`_.

            -   real: user owns the process.
            -   effective: user invoking.

        Examples:
            >>> assert Path().access() is True
            >>> assert Path('/usr/bin').access() is False

        Args:
            os_mode: Operating-system mode bitfield. Can be F_OK to test existence,
                or the inclusive-OR of R_OK, W_OK, and X_OK (default: `os.W_OK`).
            dir_fd: If not None, it should be a file descriptor open to a directory,
                and path should be relative; path will then be relative to that
                directory.
            effective_ids: If True, access will use the effective uid/gid instead of
                the real uid/gid (default: True).
            follow_symlinks: If False, and the last element of the path is a symbolic link,
                access will examine the symbolic link itself instead of the file
                the link points to (default: True).

        Note:
            Most operations will use the effective uid/gid (what the operating system
            looks at to make a decision whether you are allowed to do something), therefore this
            routine can be used in a suid/sgid environment to test if the invoking user
            has the specified access to the path.

            When a setuid program (`-rwsr-xr-x`) executes, the process changes its Effective User ID (EUID)
            from the default RUID to the owner of this special binary executable file:
                -   euid: owner of executable (`os.geteuid()`).
                -   uid: user starting the process (`os.getuid()`).

        Returns:
            True if access.

        .. _Real Effective IDs:
            https://stackoverflow.com/questions/32455684/difference-between-real-user-id-effective-user-id-and-saved-user-id
        """
        return os.access(self, mode=os_mode, dir_fd=dir_fd, effective_ids=effective_ids,
                         follow_symlinks=follow_symlinks)

    def add(self, *args, exception=False):
        """
        Add args to self.

        Examples:
            >>> import ppath
            >>>
            >>> p = Path().add('a/a')
            >>> assert Path() / 'a/a' == p
            >>> p = Path().add(*['a', 'a'])
            >>> assert Path() / 'a/a' == p
            >>> p = Path(ppath.__file__)
            >>> p.add('a', exception=True)  # doctest: +IGNORE_EXCEPTION_DETAIL, +ELLIPSIS
            Traceback (most recent call last):
            FileNotFoundError...

        Args:
            *args: parts to be added.
            exception: raise exception if self is not dir and parts can not be added (default: False).

        Raises:
            FileNotFoundError: if self is not dir and parts can not be added.

        Returns:
            Compose path.
        """
        print(self.is_file())
        if exception and self.is_file() and args:
            raise FileNotFoundError(f'parts: {args}, can not be added since path is file or not directory: {self}')
        args = toiter(args)
        path = self
        for arg in args:
            path = path / arg
        return path

    def append_text(self, text, encoding=None, errors=None):
        """
        Open the file in text mode, append to it, and close the file (creates file if not file).

        Examples:
            >>> with Path.tempfile() as tmp:
            ...    _ = tmp.path.write_text('Hello')
            ...    assert 'Hello World!' in tmp.path.append_text(' World!')

        Args:
            text: text to add.
            encoding: encoding (default: None).
            errors: raise error if there is no file (default: None).

        Returns:
            File text with text appended.
        """
        if not isinstance(text, str):
            raise TypeError(f'data must be str, not {text.__class__.__name__}')
        with self.open(mode='a', encoding=encoding, errors=errors) as f:
            f.write(text)
        return self.read_text()

    @contextlib.contextmanager
    def cd(self):
        """
        Change dir context manager to self if dir or parent if file and exists

        Examples:
            >>> new = Path('/usr/local')
            >>> p = Path.cwd()
            >>> with new.cd() as prev:
            ...     assert new == Path.cwd()
            ...     assert prev == p
            >>> assert p == Path.cwd()

        Returns:
            Old Pwd Path.
        """
        oldpwd = self.cwd()
        try:
            self.chdir()
            yield oldpwd
        finally:
            oldpwd.chdir()

    def chdir(self):
        """
        Change to self if dir or parent if file and file exists.

        Examples:
            >>> new = Path(__file__).chdir()
            >>> assert new == Path(__file__).parent
            >>> assert Path.cwd() == new
            >>>
            >>> new = Path(__file__).parent
            >>> assert Path.cwd() == new
            >>>
            >>> Path("/tmp/foo").chdir()  # doctest: +IGNORE_EXCEPTION_DETAIL
            Traceback (most recent call last):
            FileNotFoundError: ... No such file or directory: '/tmp/foo'

        Raises:
            FileNotFoundError: No such file or directory if path does not exist.

        Returns:
            Path with changed directory.
        """
        path = self.to_parent()
        os.chdir(path)
        return path

    def chmod(self, mode=None):
        subprocess.run([*self.sudo(passwd=Passwd.from_root(), to_list=True), f'{self.chmod.__name__}',
                        str(mode or (755 if self.is_dir() else 644)), self.resolve()], capture_output=True)
        return self

    def chown(self, passwd=None):
        subprocess.run(
            [*self.sudo(passwd=Passwd.from_root(), to_list=True),
             f'{self.chown.__name__}',
             f'{passwd.user}:{passwd.group}',
             self.resolve()],
            check=True, capture_output=True)
        return self

    def checksum(self, algorithm='sha256', block_size=65536):
        """
        Calculate the checksum of a file.

        Examples:
            >>> with Path.tempfile() as tmp:
            ...    _ = tmp.path.write_text('Hello')
            ...    assert tmp.path.checksum() == '185f8db32271fe25f561a6fc938b2e264306ec304eda518007d1764826381969'

        Args:
            algorithm: hash algorithm (default: 'sha256').
            block_size: block size (default: 65536).

        Returns:
            Checksum of file.
        """
        h = hashlib.new(algorithm)
        with self.open('rb') as f:
            for block in iter(lambda: f.read(block_size), b''):
                h.update(block)
        return h.hexdigest()

    def cmp(self, other):
        """
        Determine, whether two files provided to it are the same or not.
        By the same means that their contents are the same or not (excluding any metadata).
        Uses Cryptographic Hashes (using SHA256 - Secure hash algorithm 256) as a hash function.

        Examples:
            >>> import ppath
            >>> import asyncio
            >>>
            >>> assert Path(ppath.__file__).cmp(ppath.__file__) is True
            >>> assert Path(ppath.__file__).cmp(asyncio.__file__) is False

        Args:
            other: other file to compare to

        Returns:
            True if equal.
        """
        return self.checksum() == self.__class__(other).checksum()

    def cp(self, dest):
        """
        Copy

        Args:
            dest: destination.

        Returns:
            None.
        """
        subprocess.run([*self.__class__(dest).sudo(to_list=True), f'{self.cp.__name__}', '-R', str(dest)], check=True,
                       capture_output=True)

    @classmethod
    def expandvars(cls, path=None):
        """
        Return a Path instance from expanded environment variables in path.

        Expand shell variables of form $var and ${var}.
        Unknown variables are left unchanged.

        Examples:
            >>> Path.expandvars('~/repo')  # doctest: +ELLIPSIS
            Path('~/repo')
            >>> Path.expandvars('${HOME}/repo')
            Path('.../repo')

        Returns:
            Expanded Path.
        """
        return cls(os.path.expandvars(path) if path is not None else "")

    def has(self, value):
        """
        Checks all items in value exist in `self.parts` (not absolute and not relative).

        Only checks parts and not resolved as checked by __contains__ or absolute.

        Examples:
            >>> assert Path('/usr/local').has('/usr') is True
            >>> assert Path('/usr/local').has('usr local') is True
            >>> assert Path('/usr/local').has('home') is False
            >>> assert Path('/usr/local').has('') is False

        Args:
            value: space separated list of items to check, or iterable of items.

        Returns:
            bool
        """
        value = Path(value) if isinstance(value, str) and "/" in value else toiter(value)
        return all([item in self.parts for item in value])

    def mkdir(self, name='', passwd=None, mode=None, effective_ids=False):
        """
        Add directory, make directory and return new Path.

        Args:
            name: name.
            passwd: group/user.
            mode: mode.
            effective_ids: If True, access will use the effective uid/gid instead of
                the real uid/gid (default: True).

        Raises:
            NotADirectoryError: Directory can not be made because it's a file.

        Returns:
            Path:
        """
        passwd = passwd or Passwd.from_login()
        file = None
        m = ['-m', str(mode)] if mode else []
        if not (p := (self / name).resolve()).is_dir() and not (file := p._is_file()):
            print(
                [*self.sudo(to_list=True, effective_ids=effective_ids), f'{self.mkdir.__name__}', '-p', *m, p.resolve()]
            )
            subprocess.run([*self.sudo(to_list=True, effective_ids=effective_ids),
                            f'{self.mkdir.__name__}', '-p', *m, p.resolve()], capture_output=True)
        if file:
            raise NotADirectoryError(f'Directory: "{name}" can not be made because "{file=}" is a file')
        p.chown(passwd=passwd)
        return p

    def rm(self, *args, missing_ok=True, resolved=None):
        """
        Delete a folder/file (even if the folder is not empty)

        Examples:
            >>> with Path.tempdir() as tmp:
            ...     name = 'dir'
            ...     pth = tmp(name)
            ...     assert pth.is_dir()
            ...     pth.rm()
            ...     assert not pth.is_dir()
            ...     name = 'file'
            ...     pth = tmp(name, PIs.IS_FILE)
            ...     assert pth.is_file()
            ...     pth.rm()
            ...     assert not pth.is_file()
            ...     assert Path('/tmp/a/a/a/a')().is_dir()

        Args:
            *args: parts to add to self.
            missing_ok: missing_ok
            resolved: True for resolved, False for absolute and None for relative or doesn't exists (default: True).
        """
        if not missing_ok and not self.exists():
            raise

        path = self.add(*args)
        if path.exists():
            subprocess.run([*self.sudo(passwd=Passwd.from_root(), to_list=True), f'{self.rm.__name__}',
                            *(['-r'] if self.is_dir() else []),
                            self.resolve() if resolved else self.absolute() if resolved is False else self],
                           capture_output=True)

    def setid(self, name=None, uid=True):
        """
        Sets the set-user-ID-on-execution or set-group-ID-on-execution bits.

        Examples:
            >>> with Path.tempdir() as p:
            ...     a = p.touch('a')
            ...     _ = a.setid()
            ...     assert a.stats().suid is True
            ...     _ = a.setid(uid=False)
            ...     assert a.stats().sgid is True
            ...
            ...     a.rm()
            ...
            ...     _ = a.touch()
            ...     b = a.setid('b')
            ...     assert b.stats().suid is True
            ...     assert a.cmp(b) is True
            ...
            ...     _ = b.setid('b', uid=False)
            ...     assert b.stats().sgid is True
            ...
            ...     _ = a.write_text('a')
            ...     assert a.cmp(b) is False
            ...     b = a.setid('b')
            ...     assert b.stats().suid is True
            ...     assert a.cmp(b) is True

        Args:
            name: name to rename if provided.
            uid: True to set UID bit, False to set GID bit (default: True).

        Returns:
            Updated Path.
        """
        target = self.with_name(name) if name else self
        sudo = target.sudo(passwd=Passwd.from_root())
        chmod = f'{sudo} chmod -R {"u" if uid else "g"}+s,+x "{target}"'
        mod = (stat.S_ISUID if uid else stat.S_ISGID) | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
        if name and (not target.exists() or not self.cmp(target)):
            subprocess.run(f'{sudo} cp -R "{self}" "{target}" && '
                           f'{sudo} chown -R 0:0 "{target}" && {chmod}', shell=True, check=True, capture_output=True)
        elif (s := target.stats()) and not (s.result.st_mode & mod == mod):
            subprocess.run(chmod, shell=True, check=True, capture_output=True)
        return target

    def stats(self, follow_symlinks=True):
        """
        Return the result of the stat() system call on this path, like
        os.stat() does with extra parsing for bits and root.

        Examples:
            >>> rv = Path().stats()
            >>> assert all([rv.root, rv.sgid, rv.sticky, rv.suid]) is False
            >>>
            >>> with Path.tempfile() as file:
            ...     f = Path(file.name)
            ...     _ = f.chmod('u+s,+x')
            ...     assert f.stats().suid is True
            ...     _ = f.chmod('g+s,+x')
            ...     assert f.stats().sgid is True

        Args:
            follow_symlinks: If False, and the last element of the path is a symbolic link,
                stat will examine the symbolic link itself instead of the file
                the link points to (default: True).

        Returns:
            PathStat namedtuple :class:`ppath.PathStat`:
            gid: group id.
            group: group name.
            mode: file mode string formatted as '-rwxrwxrwx'
            result: result of :func:`os.stat`
            root: is owned by root
            sgid: group executable and sticky bit (GID bit), members execute as the executable group (i.e.: crontab)
            sticky: sticky bit (directories), new files created in this directory will be owned by the directory's owner
            suid: user executable and sticky bit (UID bit), user execute and as the executable owner (i.e.: sudo)
            uid: user id.
            user: user name.
        """
        mapping = dict(
            sgid=stat.S_ISGID | stat.S_IXGRP,
            suid=stat.S_ISUID | stat.S_IXUSR,
            sticky=stat.S_ISVTX,
        )
        result = os.stat(self, follow_symlinks=follow_symlinks)
        return PathStat(
            gid=result.st_gid,
            mode=stat.filemode(result.st_mode),
            result=result,
            root=result.st_uid == 0,
            uid=result.st_uid,
            **{i: result.st_mode & mapping[i] == mapping[i] for i in PathStat._fields if i in mapping.keys()}
        )

    def sudo(self, passwd=None, to_list=False, os_mode=os.W_OK, effective_ids=False, follow_symlinks=True):
        """
        Returns sudo if path is not own by user and sudo command installed.

        Examples:
            >>> su = which('sudo')
            >>> assert Path('/tmp').sudo() == ''
            >>> assert Path('/usr/bin').sudo() == '/usr/bin/sudo'
            >>> assert Path('/usr/bin/no_dir/no_file.text').sudo() == su
            >>> assert Path('no_dir/no_file.text').sudo() == ''
            >>> assert Path('/tmp').sudo(to_list=True) == []
            >>> assert Path('/tmp').sudo(passwd=Passwd.from_root(), to_list=True) == [su]
            >>> assert Path('/usr/bin').sudo(to_list=True) == [su]

        Args:
            passwd: group/user to check if root to force sudo (default: ACTUAL).
            to_list: return starred/list for cmd with no shell (default: False).
            os_mode: Operating-system mode bitfield. Can be F_OK to test existence,
                or the inclusive-OR of R_OK, W_OK, and X_OK (default: `os.W_OK`).
            effective_ids: If True, access will use the effective uid/gid instead of
                the real uid/gid (default: True).
            follow_symlinks: If False, and the last element of the path is a symbolic link,
                access will examine the symbolic link itself instead of the file
                the link points to (default: True).
        Returns:
            `sudo` or ``, str or list.
        """
        passwd = passwd or Passwd.from_login()
        rv = which()
        if rv:
            # noinspection TimingAttack
            if Passwd.from_root() != passwd:
                p = self
                while p:
                    if p.exists() and p.access(os_mode=os_mode, effective_ids=effective_ids,
                                               follow_symlinks=follow_symlinks):
                        rv = ''
                        break
                    else:
                        p = p.parent
                        if p == Path('/'):
                            break
        return ([rv] if rv else []) if to_list else rv

    @property
    def text(self) -> str:
        """
        Path as text.

        Examples:
            >>> assert Path('/usr/local').text == '/usr/local'

        Returns:
            Path string.
        """
        return str(self)

    @classmethod
    @contextlib.contextmanager
    def tempdir(cls, suffix=None, prefix=None, directory=None):
        """
        Create and return a temporary directory.  This has the same
        behavior as mkdtemp but can be used as a context manager.

        Examples:
            >>> with Path.tempdir() as tmpdir:
            ...    assert tmpdir.exists() and tmpdir.is_dir()

        Upon exiting the context, the directory and everything contained
        in it are removed.

    If 'suffix' is not None, the file name will end with that suffix,
    otherwise there will be no suffix.

    If 'prefix' is not None, the file name will begin with that prefix,
    otherwise a default prefix is used.

    If 'dir' is not None, the file will be created in that directory,
    otherwise a default directory is used.

        Args:
            suffix: If 'suffix' is not None, the directory name will end with that suffix,
                otherwise there will be no suffix. For example, .../T/tmpy5tf_0suffix
            prefix: If 'prefix' is not None, the directory name will begin with that prefix,
                otherwise a default prefix is used.. For example, .../T/prefixtmpy5tf_0
            directory: If 'directory' is not None, the directory will be created in that directory (must exist,
                otherwise a default directory is used. For example, DIRECTORY/tmpy5tf_0

        Returns:
            Directory Path.
        """
        cwd = cls.cwd()
        tmp = tempfile.TemporaryDirectory(suffix=suffix, prefix=prefix, dir=directory)
        with tmp as cd:
            try:
                yield cls(cd)
            finally:
                cwd.chdir()

    @classmethod
    @contextlib.contextmanager
    def tempfile(cls,
                 mode="w", buffering=-1, encoding=None,
                 newline=None, suffix=None, prefix=None,
                 directory=None, delete=True,
                 *, errors=None):
        """
        Create and return a temporary file.

        Examples:
            >>> with Path.tempfile() as tmpfile:
            ...    assert tmpfile.path.exists() and tmpfile.path.is_file()

        Args:
            mode: the mode argument to io.open (default "w+b").
            buffering:  the buffer size argument to io.open (default -1).
            encoding: the encoding argument to `io.open` (default None)
            newline: the newline argument to `io.open` (default None)
            delete: whether the file is deleted on close (default True).
            suffix: prefix for filename.
            prefix: prefix for filename.
            directory: directory.
            errors: the errors' argument to `io.open` (default None)

        Returns:
            An object with a file-like interface; the name of the file
            is accessible as its 'name' attribute.  The file will be automatically
            deleted when it is closed unless the 'delete' argument is set to False.
        """
        with tempfile.NamedTemporaryFile(mode=mode, buffering=buffering, encoding=encoding, newline=newline,
                                         suffix=suffix, prefix=prefix, dir=directory, delete=delete,
                                         errors=errors) as tmp:
            try:
                tmp.path = cls(tmp.name)
                yield tmp
            finally:
                pass

    def to_parent(self):
        """
        Return Parent if is file and exists or self.

        Examples:
            >>> assert Path(__file__).to_parent() == Path(__file__).parent

        Returns:
            Path of directory if is file or self.
        """
        return self.parent if self.is_file() else self

    def touch(self, name='', passwd=None, mode=None, effective_ids=False):
        """
        Add file, touch and return post_init Path.

        Parent paths are created.

        Args:
            name: name.
            passwd: group/user.
            mode: mode.
            effective_ids: If True, access will use the effective uid/gid instead of
                the real uid/gid (default: True).

        Returns:
            Path.
        """
        file = None
        passwd = passwd or Passwd.from_login()
        if not (p := (self / (name or str())).resolve()).is_file() and not p.is_dir() \
                and not (file := p.parent._is_file()):
            if not (d := p.parent).exists():
                d.mkdir(passwd=passwd, mode=mode, effective_ids=effective_ids)
            subprocess.run(
                [*self.sudo(passwd=passwd, to_list=True, effective_ids=effective_ids), f'{self.touch.__name__}', p],
                capture_output=True, check=True)
        if file:
            raise NotADirectoryError(f'{file=} is file and not dir to touch: {p=}')
        else:
            p.chmod(mode=mode)
            p.chown(passwd=passwd)
        return p

    def with_suffix(self, suffix=''):
        """
        Sets default for suffix to "", since :class:`pathlib.Path` does not have default.

        Return a new path with the file suffix changed.  If the path
        has no suffix, add given suffix.  If the given suffix is an empty
        string, remove the suffix from the path.

        Examples:
            >>> Path("/tmp/test.txt").with_suffix()
            Path('/tmp/test')

        Args:
            suffix: suffix (default: '')

        Returns:
            Path.
        """
        return super().with_suffix(suffix=suffix)


@dataclass
class Passwd:
    """
    Passwd class from either `uid` or `user`

    Args:
    ----
        uid: int
            User ID
        user: str
            Username

    Attributes:
    -----------
        gid: int
            Group ID
        gecos: str
            Full name
        group: str
            Group name
        groups: tuple(str)
            Groups list
        home: Path
            User's home
        shell: Path
            User shell
        uid: int
            User ID (default: :func:`os.getuid` current process's user id)
        user: str
            Username
    """
    uid: Union[int, str] = field(default=None)
    user: str = field(default=None)

    gid: int = field(default=None, init=False)
    gecos: str = field(default=None, init=False)
    group: str = field(default=None, init=False)
    groups: dict[str, int] = field(default=None, init=False)
    home: Path = field(default=None, init=False)
    shell: Path = field(default=None, init=False)

    def __post_init__(self):
        """
        Instance of :class:`ppath:Passwd`  from either `uid` or `user` (default: :func:`os.getuid`)

        Uses process/real id's (os.getgid, os.getuid) instead effective id's (os.geteuid, os.getegid) as default.
            - UID and GID: when login from $LOGNAME, $USER or os.getuid()
            - RUID and RGID: process real user id and group id inherit from UID and GID
                (when process start EUID and EGID and set to the same values as RUID and RGID)
            - EUID and EGID: if executable has 'setuid' or 'setgid' (i.e: ping, sudo), EUID and EGID are changed
                to the owner (setuid) or group (setgid) of the binary.
            - SUID and SGID: if executable has 'setuid' or 'setgid' (i.e: ping, sudo), SUID and SGID are saved with
                RUID and RGID to do unprivileged tasks by a privileged process (had 'setuid' or 'setgid').
                Can not be accessed in macOS with `os.getresuid()` and `os.getresgid()`

        Examples:
            >>> p = Passwd()
            >>> u = os.environ["USER"]
            >>> assert p.gid == os.getgid()
            >>> assert p.home == Path(os.environ["HOME"])
            >>> assert p.shell == Path(os.environ["SHELL"])
            >>> assert p.uid == os.getuid()
            >>> assert p.user == u
            >>> if MACOS
            ...    assert "staff" in p.groups
            ...    assert "admin" in p.groups
            ... else:
            ...    assert u in p.groups

        Errors:
            os.setuid(0)
            os.seteuid(0)
            os.setreuid(0, 0)

        os.getuid()
        os.geteuid(
        os.setuid(uid) can only be used if running as root in macOS.
        os.seteuid(euid) -> 0
        os.setreuid(ruid, euid) -> sets EUID and RUID (probar con 501, 0)

        Returns:
            Instance of :class:`ppath:Passwd`
        """
        if self.uid is None and self.user is None:
            passwd = pwd.getpwuid(os.getuid())

        elif self.user:
            passwd = pwd.getpwnam(self.user)
        else:
            passwd = pwd.getpwuid(int(self.uid))

        self.gid = passwd.pw_gid
        self.gecos = passwd.pw_gecos
        self.home = Path(passwd.pw_dir)
        self.shell = Path(passwd.pw_shell)
        self.uid = passwd.pw_uid
        self.user = passwd.pw_name

        group = grp.getgrgid(self.gid)
        self.group = group.gr_name
        self.groups = {grp.getgrgid(gid).gr_name: gid for gid in os.getgrouplist(self.user, self.gid)}
        if self.uid not in _cache_passwd:
            _cache_passwd[self.uid] = _cache_passwd[self.user] = self

    @property
    def is_su(self) -> bool:
        """Returns True if login as root, uid=0 and not `SUDO_USER`"""
        return self.uid == 0 and not bool(os.environ.get("SUDO_USER"))

    @property
    def is_sudo(self) -> bool:
        """Returns True if SUDO_USER is set"""
        return bool(os.environ.get("SUDO_USER"))

    @property
    def is_user(self) -> bool:
        """Returns True if user and not `SUDO_USER`"""
        return self.uid != 0 and not bool(os.environ.get("SUDO_USER"))

    @classmethod
    def from_login(cls):
        """Returns instance of :class:`ppath:Passwd` from '/dev/console' on macOS and `os.getlogin()` on Linux"""
        try:
            user = pathlib.Path('/dev/console').owner() if platform.system == "Darwin" else os.getlogin()
        except OSError:
            user = pathlib.Path('/proc/self/loginuid').owner()
        if user not in _cache_passwd:
            return cls(user=user)
        return _cache_passwd[user]

    @classmethod
    def from_sudo(cls):
        """Returns instance of :class:`ppath:Passwd` from `SUDO_USER` if set or current process's user"""
        uid = os.environ.get("SUDO_UID", os.getuid())
        if uid not in _cache_passwd:
            return cls(uid)
        return _cache_passwd[uid]

    @classmethod
    def from_root(cls):
        """Returns instance of :class:`ppath:Passwd` for root"""
        if 0 not in _cache_passwd:
            return cls(0)
        return _cache_passwd[0]


PathStat = collections.namedtuple('PathStat', 'gid group mode result root sgid sticky suid uid user')
PathStat.__doc__ = """
namedtuple for :func:`ppath.Path.stats`.

Args:
    gid: group id.
    group: group name.
    mode: file mode string formatted as '-rwxrwxrwx'
    result: result of os.stat
    root: is owned by root
    sgid: group executable and sticky bit (GID bit), members execute as the executable group (i.e.: crontab)
    sticky: sticky bit (directories), new files created in this directory will be owned by the directory's owner
    suid: user executable and sticky bit (UID bit), user execute and as the executable owner (i.e.: sudo)
    uid: user id.
    user: user name.
"""


def toiter(obj, always=False, split=" "):
    """
    To iter.

    Examples:
        >>> assert toiter('test1') == ['test1']
        >>> assert toiter('test1 test2') == ['test1', 'test2']
        >>> assert toiter({'a': 1}) == {'a': 1}
        >>> assert toiter({'a': 1}, always=True) == [{'a': 1}]
        >>> assert toiter('test1.test2') == ['test1.test2']
        >>> assert toiter('test1.test2', split='.') == ['test1', 'test2']
        >>> assert toiter(Path("/tmp/foo")) == ('/', 'tmp', 'foo')

    Args:
        obj: obj.
        always: return any iterable into a list.
        split: split for str.

    Returns:
        Iterable.
    """
    if isinstance(obj, str):
        obj = obj.split(split)
    elif hasattr(obj, "parts"):
        obj = obj.parts
    elif not isinstance(obj, Iterable) or always:
        obj = [obj]
    return obj


def which(cmd="sudo"):
    """
    Checks if cmd or path is executable or exported bash function.

    Examples:
        >>> assert which() == '/usr/bin/sudo'
        >>> assert which('/usr/local') == ''
        >>> assert which('/usr/bin/sudo') == '/usr/bin/sudo'
        >>> assert which('subprocess_test') == 'subprocess_test'
        >>> assert which('let') == 'let'
        >>> assert which('source') == 'source'

    Args:
        cmd: command or path.

    Returns:
        Cmd path.
    """
    key = Path(cmd).name
    if key not in _cache_which:
        value = shutil.which(cmd, mode=os.X_OK) or subprocess.run(
            f'command -v {cmd}', shell=True, text=True, capture_output=True).stdout.rstrip('\n') or ''
        _cache_which[key] = value
    return _cache_which[key]

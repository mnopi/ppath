# coding=utf-8
"""
Ppath package
"""
__all__ = (
    "Path",
    "toiter",
)
import contextlib
import hashlib
import os
import pathlib
import tempfile
from collections.abc import Iterable


class Path(pathlib.Path, pathlib.PurePosixPath):

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
        path = self.directory()
        os.chdir(path)
        return path

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

    def directory(self):
        """
        Return Parent if is file and exists or self.

        Examples:
            >>> assert Path(__file__).directory() == Path(__file__).parent

        Returns:
            Path of directory if is file or self.
        """
        return self.parent if self.is_file() else self

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

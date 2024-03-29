# -*- coding: utf-8 -*-
"""
tests/test-uploads.py
=====================
This is a Nose testing file for Flask-Uploads.

NOTE: While Flask-Uploads will probably work on Windows, all the filenames in
this testing file are in the POSIX style. So, no guarantees that the tests
will pass.

:copyright: 2010 Matthew "LeafStorm" Frazier
:license:   MIT/X11, see LICENSE for details
"""

from __future__ import with_statement
import unittest
import os.path
from flask import Flask, url_for
from flask_uploads import (UploadSet, UploadConfiguration, extension,
    lowercase_ext, TestingFileStorage, patch_request_class, configure_uploads,
    addslash, ALL, AllExcept)


class TestMiscellaneous(object):
    def test_tfs(self):
        tfs = TestingFileStorage(filename='foo.bar')
        assert tfs.filename == 'foo.bar'
        assert tfs.name is None
        assert tfs.saved is None
        tfs.save('foo_bar.txt')
        assert tfs.saved == 'foo_bar.txt'

    def test_extension(self):
        assert extension('foo.txt') == 'txt'
        assert extension('foo') == ''
        assert extension('archive.tar.gz') == 'gz'
        assert extension('audio.m4a') == 'm4a'

    def test_lowercase_ext(self):
        assert lowercase_ext('foo.txt') == 'foo.txt'
        assert lowercase_ext('FOO.TXT') == 'FOO.txt'
        assert lowercase_ext('foo') == 'foo'
        assert lowercase_ext('FOO') == 'FOO'
        assert lowercase_ext('archive.tar.gz') == 'archive.tar.gz'
        assert lowercase_ext('ARCHIVE.TAR.GZ') == 'ARCHIVE.TAR.gz'
        assert lowercase_ext('audio.m4a') == 'audio.m4a'
        assert lowercase_ext('AUDIO.M4A') == 'AUDIO.m4a'

    def test_addslash(self):
        assert (addslash('http://localhost:4000') ==
                'http://localhost:4000/')
        assert (addslash('http://localhost/uploads') ==
                'http://localhost/uploads/')
        assert (addslash('http://localhost:4000/') ==
                'http://localhost:4000/')
        assert (addslash('http://localhost/uploads/') ==
                'http://localhost/uploads/')

    def test_custom_iterables(self):
        assert 'txt' in ALL
        assert 'exe' in ALL
        ax = AllExcept(['exe'])
        assert 'txt' in ax
        assert 'exe' not in ax


Config = UploadConfiguration

class TestConfiguration(object):
    def setup(self):
        self.app = Flask(__name__)

    def teardown(self):
        del self.app

    def configure(self, *sets, **options):
        self.app.config.update(options)
        configure_uploads(self.app, sets)
        return self.app.upload_set_config

    def test_manual(self):
        f, p = UploadSet('files'), UploadSet('photos')
        setconfig = self.configure(f, p,
            UPLOADED_FILES_DEST = '/var/files',
            UPLOADED_FILES_URL = 'http://localhost:6001/',
            UPLOADED_PHOTOS_DEST = '/mnt/photos',
            UPLOADED_PHOTOS_URL = 'http://localhost:6002/'
        )
        fconf, pconf = setconfig['files'], setconfig['photos']
        assert fconf == Config('/var/files', 'http://localhost:6001/')
        assert pconf == Config('/mnt/photos', 'http://localhost:6002/')

    def test_selfserve(self):
        f, p = UploadSet('files'), UploadSet('photos')
        setconfig = self.configure(f, p,
            UPLOADED_FILES_DEST = '/var/files',
            UPLOADED_PHOTOS_DEST = '/mnt/photos'
        )
        fconf, pconf = setconfig['files'], setconfig['photos']
        assert fconf == Config('/var/files', None)
        assert pconf == Config('/mnt/photos', None)

    def test_defaults(self):
        f, p = UploadSet('files'), UploadSet('photos')
        setconfig = self.configure(f, p,
            UPLOADS_DEFAULT_DEST = '/var/uploads',
            UPLOADS_DEFAULT_URL = 'http://localhost:6000/'
        )
        fconf, pconf = setconfig['files'], setconfig['photos']
        assert fconf == Config('/var/uploads/files',
                               'http://localhost:6000/files/')
        assert pconf == Config('/var/uploads/photos',
                               'http://localhost:6000/photos/')

    def test_default_selfserve(self):
        f, p = UploadSet('files'), UploadSet('photos')
        setconfig = self.configure(f, p,
            UPLOADS_DEFAULT_DEST = '/var/uploads'
        )
        fconf, pconf = setconfig['files'], setconfig['photos']
        assert fconf == Config('/var/uploads/files', None)
        assert pconf == Config('/var/uploads/photos', None)

    def test_mixed_defaults(self):
        f, p = UploadSet('files'), UploadSet('photos')
        setconfig = self.configure(f, p,
            UPLOADS_DEFAULT_DEST = '/var/uploads',
            UPLOADS_DEFAULT_URL = 'http://localhost:6001/',
            UPLOADED_PHOTOS_DEST = '/mnt/photos',
            UPLOADED_PHOTOS_URL = 'http://localhost:6002/'
        )
        fconf, pconf = setconfig['files'], setconfig['photos']
        assert fconf == Config('/var/uploads/files',
                               'http://localhost:6001/files/')
        assert pconf == Config('/mnt/photos', 'http://localhost:6002/')

    def test_defaultdest_callable(self):
        f = UploadSet('files', default_dest=lambda app: os.path.join(
            app.config['INSTANCE'], 'files'
        ))
        p = UploadSet('photos')
        setconfig = self.configure(f, p,
            INSTANCE = '/home/me/webapps/thisapp',
            UPLOADED_PHOTOS_DEST = '/mnt/photos',
            UPLOADED_PHOTOS_URL = 'http://localhost:6002/'
        )
        fconf, pconf = setconfig['files'], setconfig['photos']
        assert fconf == Config('/home/me/webapps/thisapp/files', None)
        assert pconf == Config('/mnt/photos', 'http://localhost:6002/')


class TestPreconditions(object):
    def test_filenames(self):
        uset = UploadSet('files')
        uset._config = Config('/uploads')
        namepairs = (
            ('foo.txt', True),
            ('boat.jpg', True),
            ('warez.exe', False)
        )
        for name, result in namepairs:
            tfs = TestingFileStorage(filename=name)
            assert uset.file_allowed(tfs, name) is result

    def test_default_extensions(self):
        uset = UploadSet('files')
        uset._config = Config('/uploads')
        extpairs = (('txt', True), ('jpg', True), ('exe', False))
        for ext, result in extpairs:
            assert uset.extension_allowed(ext) is result


class TestSaving(object):
    def setup(self):
        self.old_makedirs = os.makedirs
        os.makedirs = lambda v: None

    def teardown(self):
        os.makedirs = self.old_makedirs
        del self.old_makedirs

    def test_saved(self):
        uset = UploadSet('files')
        uset._config = Config('/uploads')
        tfs = TestingFileStorage(filename='foo.txt')
        res = uset.save(tfs)
        assert res == 'foo.txt'
        assert tfs.saved == '/uploads/foo.txt'

    def test_save_folders(self):
        uset = UploadSet('files')
        uset._config = Config('/uploads')
        tfs = TestingFileStorage(filename='foo.txt')
        res = uset.save(tfs, folder='someguy')
        assert res == 'someguy/foo.txt'
        assert tfs.saved == '/uploads/someguy/foo.txt'

    def test_save_named(self):
        uset = UploadSet('files')
        uset._config = Config('/uploads')
        tfs = TestingFileStorage(filename='foo.txt')
        res = uset.save(tfs, name='file_123.txt')
        assert res == 'file_123.txt'
        assert tfs.saved == '/uploads/file_123.txt'

    def test_save_namedext(self):
        uset = UploadSet('files')
        uset._config = Config('/uploads')
        tfs = TestingFileStorage(filename='boat.jpg')
        res = uset.save(tfs, name='photo_123.')
        assert res == 'photo_123.jpg'
        assert tfs.saved == '/uploads/photo_123.jpg'

    def test_folder_namedext(self):
        uset = UploadSet('files')
        uset._config = Config('/uploads')
        tfs = TestingFileStorage(filename='boat.jpg')
        res = uset.save(tfs, folder='someguy', name='photo_123.')
        assert res == 'someguy/photo_123.jpg'
        assert tfs.saved == '/uploads/someguy/photo_123.jpg'

    def test_implicit_folder(self):
        uset = UploadSet('files')
        uset._config = Config('/uploads')
        tfs = TestingFileStorage(filename='boat.jpg')
        res = uset.save(tfs, name='someguy/photo_123.')
        assert res == 'someguy/photo_123.jpg'
        assert tfs.saved == '/uploads/someguy/photo_123.jpg'

    def test_secured_filename(self):
        uset = UploadSet('files', ALL)
        uset._config = Config('/uploads')
        tfs1 = TestingFileStorage(filename='/etc/passwd')
        tfs2 = TestingFileStorage(filename='../../myapp.wsgi')
        res1 = uset.save(tfs1)
        assert res1 == 'etc_passwd'
        assert tfs1.saved == '/uploads/etc_passwd'
        res2 = uset.save(tfs2)
        assert res2 == 'myapp.wsgi'
        assert tfs2.saved == '/uploads/myapp.wsgi'


class TestConflictResolution(object):
    def setup(self):
        self.extant_files = []
        self.old_exists = os.path.exists
        os.path.exists = self.exists
        self.old_makedirs = os.makedirs
        os.makedirs = lambda v: None

    def teardown(self):
        os.path.exists = self.old_exists
        del self.extant_files, self.old_exists
        os.makedirs = self.old_makedirs
        del self.old_makedirs

    def extant(self, *files):
        self.extant_files.extend(files)

    def exists(self, fname):
        return fname in self.extant_files

    def test_self(self):
        assert not os.path.exists('/uploads/foo.txt')
        self.extant('/uploads/foo.txt')
        assert os.path.exists('/uploads/foo.txt')

    def test_conflict(self):
        uset = UploadSet('files')
        uset._config = Config('/uploads')
        tfs = TestingFileStorage(filename='foo.txt')
        self.extant('/uploads/foo.txt')
        res = uset.save(tfs)
        assert res == 'foo_1.txt'

    def test_multi_conflict(self):
        uset = UploadSet('files')
        uset._config = Config('/uploads')
        tfs = TestingFileStorage(filename='foo.txt')
        self.extant('/uploads/foo.txt',
                    *('/uploads/foo_%d.txt' % n for n in range(1, 6)))
        res = uset.save(tfs)
        assert res == 'foo_6.txt'

    def test_conflict_without_extension(self):
        # Test case for issue #7.
        uset = UploadSet('files', extensions=(''))
        uset._config = Config('/uploads')
        tfs = TestingFileStorage(filename='foo')
        self.extant('/uploads/foo')
        res = uset.save(tfs)
        assert res == 'foo_1'


class TestPathsAndURLs(object):
    def test_path(self):
        uset = UploadSet('files')
        uset._config = Config('/uploads')
        assert uset.path('foo.txt') == '/uploads/foo.txt'
        assert uset.path('someguy/foo.txt') == '/uploads/someguy/foo.txt'
        assert (uset.path('foo.txt', folder='someguy') ==
                '/uploads/someguy/foo.txt')
        assert (uset.path('foo/bar.txt', folder='someguy') ==
                '/uploads/someguy/foo/bar.txt')

    def test_url_generated(self):
        app = Flask(__name__)
        app.config.update(
            UPLOADED_FILES_DEST='/uploads'
        )
        uset = UploadSet('files')
        configure_uploads(app, uset)
        with app.test_request_context():
            url = uset.url('foo.txt')
            gen = url_for('_uploads.uploaded_file', setname='files',
                          filename='foo.txt', _external=True)
            assert url == gen

    def test_url_based(self):
        app = Flask(__name__)
        app.config.update(
            UPLOADED_FILES_DEST='/uploads',
            UPLOADED_FILES_URL='http://localhost:5001/'
        )
        uset = UploadSet('files')
        configure_uploads(app, uset)
        with app.test_request_context():
            url = uset.url('foo.txt')
            assert url == 'http://localhost:5001/foo.txt'
        assert '_uploads' not in app.modules


if __name__ == '__main__':
	unittest.main()
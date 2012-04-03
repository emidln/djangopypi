"""
Management command for adding a package to the repository. Supposed to be the
equivelant of calling easy_install, but the install target is the chishop.
"""

from __future__ import with_statement
import os
import tempfile
import shutil

import pkginfo

from django.core.files.base import File
from django.core.management.base import LabelCommand
from contextlib import contextmanager
from setuptools.package_index import PackageIndex
from djangopypi.models import Package, Release, Distribution


@contextmanager
def tempdir():
    """Simple context that provides a temporary directory that is deleted
    when the context is exited."""
    d = tempfile.mkdtemp(".tmp", "djangopypi.")
    yield d
    shutil.rmtree(d)


class Command(LabelCommand):
    help = """Add one or more packages to the repository. Each argument can
be a package name or a URL to an archive or egg. Package names honour
the same rules as easy_install with regard to indicating versions etc.
"""

    def __init__(self, *args, **kwargs):
        self.pypi = PackageIndex()
        LabelCommand.__init__(self, *args, **kwargs)

    def handle_label(self, label, **options):
        with tempdir() as tmp:
            path = self.pypi.download(label, tmp)
            if path:
                self._save_package(path)
            else:
                print "Could not add %s. Not found." % label

    def _save_package(self, path):
        meta = self._get_meta(path)

        try:
            package = Package.objects.create(name=meta.name)
            isnewpackage = False
        except Package.DoesNotExist:
            package = Package(name=meta.name)
            isnewpackage = True

        release = package.get_release(meta.version)
        if not isnewpackage and release and release.version == meta.version:
            print "%s-%s already added" % (meta.name, meta.version)
            return

        release = Release()
        release.version = meta.version
        release.package = package

        for key in meta:
            release.package_info[key] = getattr(meta, key)

        release.save()

        distribution = Distribution(release=release)

        filename = os.path.basename(path)
        file = File(open(path, "rb"))
        distribution.content.save(filename, file)

        distribution.save()

        print "%s-%s added" % (meta.name, meta.version)

    def _get_meta(self, path):
        data = pkginfo.get_metadata(path)
        if data:
            return data
        else:
            print "Couldn't get metadata from %s. Not added to chishop" % os.path.basename(path)
            return None

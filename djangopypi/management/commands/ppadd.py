"""
Management command for adding a package to the repository. Supposed to be the
equivelant of calling easy_install, but the install target is the chishop.
"""

from __future__ import with_statement
import os
import tempfile
import shutil
import urllib

import pkginfo

from django.core.files.base import File
from django.core.management.base import LabelCommand
from optparse import make_option
from contextlib import contextmanager
from urlparse import urlsplit
from setuptools.package_index import PackageIndex
from django.contrib.auth.models import User
from djangopypi.models import Package, Release, Classifier, Distribution





@contextmanager
def tempdir():
    """Simple context that provides a temporary directory that is deleted
    when the context is exited."""
    d = tempfile.mkdtemp(".tmp", "djangopypi.")
    yield d
    shutil.rmtree(d)

class Command(LabelCommand):
    option_list = LabelCommand.option_list + (
            make_option("-o", "--owner", help="add packages as OWNER",
                        metavar="OWNER", default=None),
        )
    help = """Add one or more packages to the repository. Each argument can
be a package name or a URL to an archive or egg. Package names honour
the same rules as easy_install with regard to indicating versions etc.

If a version of the package exists, but is older than what we want to install,
the owner remains the same.

For new packages there needs to be an owner. If the --owner option is present
we use that value. If not, we try to match the maintainer of the package, form
the metadata, with a user in out database, based on the If it's a new package
and the maintainer emailmatches someone in our user list, we use that. If not,
the package can not be
added"""

    def __init__(self, *args, **kwargs):
        self.pypi = PackageIndex()
        LabelCommand.__init__(self, *args, **kwargs)

    def handle_label(self, label, **options):
        with tempdir() as tmp:
            path = self.pypi.download(label, tmp)
            if path:
                self._save_package(path, options["owner"])
            else:
                print "Could not add %s. Not found." % label

    def _save_package(self, path, ownerid):
        meta = self._get_meta(path)

        try:
            # can't use get_or_create as that demands there be an owner
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

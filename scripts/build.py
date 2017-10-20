from __future__ import print_function
import fnmatch
import os
import sys
import shutil
import tarfile
import urllib.parse as urlparse
import yaml

from contextlib import contextmanager
from pathlib import Path
from subprocess import check_call
from tempfile import TemporaryDirectory as tempdir

from conda.exports import download, hashsum_file
import pickle

config = {}
versions = ['7.5', '8.0', '9.0']
for v in versions:
    config[v] = {'linux': {}, 'windows': {}, 'osx': {}}


# The config dictionary looks like:
# config[cuda_version(s)...]
#
# and for each cuda_version the keys:
# base_url the base url for all downloads
# patch_url_ext the extra path needed to reach the patch directory from base_url
# installers_url_ext the extra path needed to reach the local installers directory
# md5_url the url for checksums
# cuda_libraries the libraries to copy in
# libdevice_versions the library device versions supported (.bc files)
# linux the linux platform config (see below)
# windows the windows platform config (see below)
# osx the osx platform config (see below)
#
# For each of the 3 platform specific dictionaries linux, windows, osx
# a dictionary containing keys:
# blob the name of the downloaded file, for linux this is the .run file
# patches a list of the patch files for the blob, they are applied in order
# cuda_lib_fmt string format for the cuda libraries
# nvvm_lib_fmt string format for the nvvm libraries
# libdevice_lib_fmt string format for the libdevice.compute bitcode file
#
# To accommodate nvtoolsext not being present as a DLL in the installer PE32s on windows,
# the windows variant of this script supports assembly directly from a pre-installed 
# CUDA toolkit. The environment variable "NVTOOLSEXT_INSTALL_PATH" can be set to the
# installation path of the CUDA toolkit's NvToolsExt location (this is not the user
# defined install directory) and the DLL will be taken from that location.



######################
### CUDA 7.5 setup ###
######################

cu_75 = config['7.5']
cu_75['base_url'] = "http://developer.download.nvidia.com/compute/cuda/7.5/Prod/"
cu_75['patch_url_ext'] = ''
cu_75['installers_url_ext'] = 'local_installers/'
cu_75['md5_url'] = "http://developer.download.nvidia.com/compute/cuda/7.5/Prod/docs/sidebar/md5sum.txt"
cu_75['pkg_libs'] = {
    'cudart': ['cudart'],
    'cufft': ['cufft'],
    'cublas': ['cublas'],
    'cusparse': ['cusparse'],
    'cusolver': ['cusolver'],
    'curand': ['curand'],
    'npp': ['nppc', 'nppi', 'npps'],
    'nvblas': ['nvblas'],
    'nvrtc': ['nvrtc', 'nvrtc-builtins'],
    'nvvm': ['nvvm', '20.10', '30.10', '35.10', '50.10'],
    'cupti': ['cupti']
    }
cu_75['libdevice_versions'] = ['20.10', '30.10', '35.10', '50.10']

cu_75['linux'] = {'blob': 'cuda_7.5.18_linux.run',
                  'patches': [],
                  'cuda_lib_fmt': 'lib{0}.so.7.5',
                  'nvvm_lib_fmt': 'lib{0}.so.3.0.0',
                  'libdevice_lib_fmt': 'libdevice.compute_{0}.bc'
                  }

cu_75['windows'] = {'blob': 'cuda_7.5.18_win10.exe',
                    'patches': [],
                    'cuda_lib_fmt': '{0}64_75.dll',
                    'nvvm_lib_fmt': '{0}64_30_0.dll',
                    'libdevice_lib_fmt': 'libdevice.compute_{0}.bc'
                    }

cu_75['osx'] = {'blob': 'cuda_7.5.27_mac.dmg',
                'patches': [],
                'cuda_lib_fmt': 'lib{0}.7.5.dylib',
                'nvvm_lib_fmt': 'lib{0}.3.0.0.dylib',
                'libdevice_lib_fmt': 'libdevice.compute_{0}.bc'
                }

######################
### CUDA 8.0 setup ###
######################

cu_8 = config['8.0']
cu_8['base_url'] = "https://developer.nvidia.com/compute/cuda/8.0/Prod2/"
cu_8['installers_url_ext'] = 'local_installers/'
cu_8['patch_url_ext'] = 'patches/2/'
cu_8['md5_url'] = "https://developer.nvidia.com/compute/cuda/8.0/Prod2/docs/sidebar/md5sum-txt"
cu_8['pkg_libs'] = {
    'cudart': ['cudart'],
    'cufft': ['cufft'],
    'cublas': ['cublas'],
    'cusparse': ['cusparse'],
    'curand': ['curand'],
    'cusolver': ['cusolver'],
    'npp': ['nppc', 'nppi', 'npps'],
    'nvrtc': ['nvrtc', 'nvrtc-builtins'],
    'nvblas': ['nvblas'],
    'nvgraph': ['nvgraph'],
    'cupti': ['cupti'],
    'nvtx': ['nvToolsExt'], # Change package name to nvToolsExt?
    'nvvm': ['nvvm', '20.10', '30.10', '35.10', '50.10'],
    }
cu_8['libdevice_versions'] = ['20.10', '30.10', '35.10', '50.10']

cu_8['linux'] = {'blob': 'cuda_8.0.61_375.26_linux-run',
                 'patches': ['cuda_8.0.61.2_linux-run'],
                 # need globs to handle symlinks
                 'cuda_lib_fmt': 'lib{0}.so*',
                 'nvtoolsext_fmt': 'lib{0}.so*',
                 'nvvm_lib_fmt': 'lib{0}.so*',
                 'libdevice_lib_fmt': 'libdevice.compute_{0}.bc'
                 }

cu_8['windows'] = {'blob': 'cuda_8.0.61_windows-exe',
                   'patches': ['cuda_8.0.61.2_windows-exe'],
                   'cuda_lib_fmt': '{0}64_80.dll',
                   'nvtoolsext_fmt': '{0}64_1.dll',
                   'nvvm_lib_fmt': '{0}64_31_0.dll',
                   'libdevice_lib_fmt': 'libdevice.compute_{0}.bc',
                   'NvToolsExtPath' :
                       os.path.join('c:' + os.sep, 'Program Files',
                                    'NVIDIA Corporation', 'NVToolsExt', 'bin')
                   }

cu_8['osx'] = {'blob': 'cuda_8.0.61_mac-dmg',
               'patches': ['cuda_8.0.61.2_mac-dmg'],
               'cuda_lib_fmt': 'lib{0}.8.0.dylib',
               'nvtoolsext_fmt': 'lib{0}.1.dylib',
               'nvvm_lib_fmt': 'lib{0}.3.1.0.dylib',
               'libdevice_lib_fmt': 'libdevice.compute_{0}.bc'
               }


# CUDA 9.0 setup
# TODO


class Extractor(object):
    """Extractor base class, platform specific extractors should inherit
    from this class.
    """

    libdir = {'linux': 'lib',
              'osx': 'lib',
              'windows': os.path.join('Library', 'bin')}

    def __init__(self, version, ver_config, plt_config):
        """Initialise an instance:
        Arguments:
          version - CUDA version string
          ver_config - the configuration for this CUDA version
          plt_config - the configuration for this platform
        """
        self.cu_version = version
        self.md5_url = ver_config['md5_url']
        self.base_url = ver_config['base_url']
        self.patch_url_ext = ver_config['patch_url_ext']
        self.installers_url_ext = ver_config['installers_url_ext']
        self.libdevice_versions = ver_config['libdevice_versions']
        self.pkg_dict = ver_config['pkg_libs']
        self.cu_blob = plt_config['blob']
        self.cuda_lib_fmt = plt_config['cuda_lib_fmt']
        self.nvtoolsext_fmt = plt_config.get('nvtoolsext_fmt')
        self.nvvm_lib_fmt = plt_config['nvvm_lib_fmt']
        self.libdevice_lib_fmt = plt_config['libdevice_lib_fmt']
        self.patches = plt_config['patches']
        self.nvtoolsextpath = plt_config.get('NvToolsExtPath')
        self.config = {'version': version, **ver_config}
        self.prefix = os.environ['PREFIX']
        self.src_dir = os.environ['SRC_DIR']
        self.output_dir = os.path.join(self.prefix, self.libdir[getplatform()])
        self.symlinks = getplatform() == 'linux'
        try:
            os.mkdir(self.output_dir)
        except FileExistsError:
            pass

    def create_link_scripts(self, pkg_name):
        pass

    def download_blobs(self):
        """Downloads the binary blobs to the $SRC_DIR
        """
        dl_url = urlparse.urljoin(self.base_url, self.installers_url_ext)
        dl_url = urlparse.urljoin(dl_url, self.cu_blob)
        dl_path = os.path.join(self.src_dir, self.cu_blob)
        if not os.path.isfile(dl_path):
            print("downloading %s to %s" % (dl_url, dl_path))
            download(dl_url, dl_path)
        else:
            print("Using existing downloaded file: %s" % dl_path)
        for p in self.patches:
            dl_url = urlparse.urljoin(self.base_url, self.patch_url_ext)
            dl_url = urlparse.urljoin(dl_url, p)
            dl_path = os.path.join(self.src_dir, p)
            if not os.path.isfile(dl_path):
                print("downloading %s to %s" % (dl_url, dl_path))
                download(dl_url, dl_path)
            else:
                print("Using existing downloaded patch: %s" % dl_path)

    def check_md5(self):
        """Checks the md5sums of the downloaded binaries
        """
        md5file = self.md5_url.split('/')[-1]
        path = os.path.join(self.src_dir, md5file)
        download(self.md5_url, path)

        # compute hash of blob
        blob_path = os.path.join(self.src_dir, self.cu_blob)
        md5sum = hashsum_file(blob_path, 'md5')

        # get checksums
        with open(md5file, 'r') as f:
            checksums = [x.strip().split() for x in f.read().splitlines() if x]

        # check md5 and filename match up
        check_dict = {x[0]: x[1] for x in checksums}
        assert check_dict[md5sum].startswith(self.cu_blob[:-7])

    def copy(self, *args):
        """The method to copy extracted files into the conda package platform
        specific directory. Platform specific extractors must implement.
        """
        raise RuntimeError('Must implement')

    def extract(self, *args):
        """The method to extract files from the cuda binary blobs.
        Platform specific extractors must implement.
        """
        raise RuntimeError('Must implement')

    def get_paths(self, libraries, dirpath, template, pkg_filter=None):
        """Gets the paths to the various cuda libraries and bc files
        """
        pathlist = []
        for libname in libraries:
            filename = template.format(libname)
            paths = fnmatch.filter(os.listdir(dirpath), filename)
            if not paths:
                msg = ("Cannot find item: %s, looked for %s" %
                       (libname, filename))
                raise RuntimeError(msg)
            if (not self.symlinks) and (len(paths) != 1):
                msg = ("Aliasing present for item: %s, looked for %s" %
                       (libname, filename))
                msg += ". Found: \n"
                msg += ', \n'.join([str(x) for x in paths])
                raise RuntimeError(msg)
            pathsforlib = []
            for path in paths:
                tmppath = os.path.join(dirpath, path)
                assert os.path.isfile(tmppath), 'missing {0}'.format(tmppath)
                pathsforlib.append(tmppath)
            if self.symlinks: # deal with symlinked items
                # get all DSOs
                concrete_dsos = [x for x in pathsforlib 
                                 if not os.path.islink(x)]
                # find the most recent library version by name
                target_library = max(concrete_dsos)
                # remove this from the list of concrete_dsos
                # all that remains are DSOs that are not wanted
                concrete_dsos.remove(target_library)
                # drop the unwanted DSOs from the paths
                [pathsforlib.remove(x) for x in concrete_dsos]
            pathlist.extend(pathsforlib)
        return pathlist

    def copy_files(self, pkg_name, cuda_lib_dir, nvvm_lib_dir, libdevice_lib_dir):
        """Copies the various cuda libraries and bc files to the output_dir
        """
        if pkg_name == 'cudatoolkit':
            return
        filepaths = self._get_filepaths(pkg_name, cuda_lib_dir, nvvm_lib_dir, libdevice_lib_dir)
        for fn in filepaths:
            if os.path.islink(fn):
                # replicate symlinks
                symlinktarget = os.readlink(fn)
                targetname = os.path.basename(fn)
                symlink = os.path.join(self.output_dir, targetname)
                print('linking %s to %s' % (symlinktarget, symlink))
                os.symlink(symlinktarget, symlink)
            else:
                print('copying %s to %s' % (fn, self.output_dir))
                shutil.copy(fn, self.output_dir)

    def _get_filepaths(self, pkg_name, cuda_lib_dir, nvvm_lib_dir, libdevice_lib_dir):
        filepaths = []
        # nvToolsExt (nvtx) and nvvm are different from the rest of the cuda libraries,
        # it follows a different naming convention, this accommodates...
        if pkg_name == 'nvtx':
            filepaths += self.get_paths(self.pkg_dict[pkg_name], cuda_lib_dir,
                                        self.nvtoolsext_fmt)
        elif pkg_name == 'nvvm':
            filepaths += self.get_paths(('nvvm',), nvvm_lib_dir, self.nvvm_lib_fmt)
            filepaths += self.get_paths(self.libdevice_versions, libdevice_lib_dir,
                                        self.libdevice_lib_fmt)
        else:
            filepaths += self.get_paths(self.pkg_dict[pkg_name], cuda_lib_dir,
                                        self.cuda_lib_fmt)
        return filepaths

    def dump_config(self, pkg_name):
        """Dumps the config dictionary into the output directory
        """
        dumpfile = os.path.join(self.output_dir, '{}_config.yaml'.format(pkg_name))
        with open(dumpfile, 'w') as f:
            yaml.dump(self.config, f, default_flow_style=False)


class WindowsExtractor(Extractor):
    """The windows extractor
    """

    def copy(self, pkg_name):
        self.copy_files(pkg_name,
            cuda_lib_dir=self.store,
            nvvm_lib_dir=self.store,
            libdevice_lib_dir=self.store)

    def make_link_scripts(self, pkg_name):
        if pkg_name == 'cudatoolkit':
            self._create_cudatoolkit_link_scripts()


    def _create_cudatoolkit_link_scripts(self):
        # Can this be pulled from meta.yaml?
        cudatoolkit_numba_deps = ['cudart', 'cufft', 'cublas',
                                  'cusparse', 'curand', 'cusolver',
                                  'npp', 'nvrtc', 'nvvm']
        post_link_lines = []
        pre_unlink_lines = []
        post_link_template = ("mklink /H %PREFIX%\\DLLs\\{0} "
                              "%PREFIX%\Library\\bin\\{0} "
                              ">> %PREFIX%\\.messages.txt")
        pre_unlink_template = ("del %PREFIX%\\DLLs\\{0} "
                               ">> %PREFIX%\\.messages.txt")
        for dep in cudatoolkit_numba_deps:
            filepaths = self._get_filepaths(dep, self.store,
                                            self.store, self.store)
            fns = [os.path.basename(filepath) for filepath in filepaths]
            post_link_lines += (post_link_template.format(fn) for fn in fns)
            pre_unlink_lines += (pre_unlink_template.format(fn) for fn in fns)
        print("Post-Link Commands:\n")
        print("\n".join(post_link_lines))
        print("Pre-Unlink Link Commands:\n")
        print("\n".join(post_link_lines))
        post_link_fn = os.path.join(self.prefix, "Scripts",
                                    ".cudatoolkit-post-link.bat")
        pre_unlink_fn = os.path.join(self.prefix, "Scripts",
                                    ".cudatoolkit-pre-unlink.bat")
        with open(post_link_fn, "w") as post_link_file:
            for line in post_link_lines:
                post_link_file.write("{}\n".format(line))
        with open(pre_unlink_fn, "w") as pre_unlink_file:
            for line in pre_unlink_lines:
                pre_unlink_file.write("{}\n".format(line))


    def extract(self, extract_dir):
        runfile = self.cu_blob
        patches = self.patches
        try:
            extract_name = '__extracted'
            extractdir = os.path.join(extract_dir, extract_name)
            store_name = 'DLLs'
            self.store = os.path.join(extract_dir, store_name)
            try:
                os.mkdir(extractdir)
                check_call(['7za', 'x', '-o%s' %
                            extractdir, os.path.join(self.src_dir, runfile)])
                for p in patches:
                    check_call(['7za', 'x', '-aoa', '-o%s' %
                                extractdir, os.path.join(self.src_dir, p)])
            except FileExistsError:
                print("Files already extracted.")

                
            nvt_path = os.environ.get('NVTOOLSEXT_INSTALL_PATH', self.nvtoolsextpath)
            print("NvToolsExt path: %s" % nvt_path)
            if nvt_path is not None:
                if not Path(nvt_path).is_dir():
                    msg = ("NVTOOLSEXT_INSTALL_PATH is invalid "
                            "or inaccessible.")
                    raise ValueError(msg)
                
            # fetch all the dlls into DLLs
            try:
                os.mkdir(self.store)
                for path, dirs, files in os.walk(extractdir):
                    if 'jre' not in path:  # don't get jre dlls
                        for filename in fnmatch.filter(files, "*.dll"):
                            if not Path(os.path.join(
                                    self.store, filename)).is_file():
                                shutil.copy(
                                    os.path.join(path, filename),
                                    self.store)
                        for filename in fnmatch.filter(files, "*.bc"):
                            if not Path(os.path.join(
                                    self.store, filename)).is_file():
                                shutil.copy(
                                    os.path.join(path, filename),
                                    self.store)
                if nvt_path is not None:
                    for path, dirs, files in os.walk(nvt_path):
                        for filename in fnmatch.filter(files, "*.dll"):
                            if not Path(os.path.join(
                                    self.store, filename)).is_file():
                                shutil.copy(
                                    os.path.join(path, filename),
                                    self.store)
            except FileExistsError:
                print("Files already copied into store.")
        except PermissionError:
            # TODO: fix this
            # cuda 8 has files that refuse to delete, figure out perm changes
            # needed and apply them above, tempdir context exit fails to rmtree
            pass


class LinuxExtractor(Extractor):
    """The linux extractor
    """

    def copy(self, pkg_name):
        basepath = self.store
        self.copy_files(pkg_name,
            cuda_lib_dir=os.path.join(
                basepath, 'lib64'), nvvm_lib_dir=os.path.join(
                basepath, 'nvvm', 'lib64'), libdevice_lib_dir=os.path.join(
                basepath, 'nvvm', 'libdevice'))

    def extract(self, extract_dir):
        runfile = self.cu_blob
        patches = self.patches
        os.chmod(runfile, 0o777)
        check_call([os.path.join(self.src_dir, runfile),
                    '--toolkitpath', extract_dir, '--toolkit', '--silent'])
        for p in patches:
            os.chmod(p, 0o777)
            check_call([os.path.join(self.src_dir, p),
                        '--installdir', extract_dir, '--accept-eula', '--silent'])
        self.store = extract_dir


@contextmanager
def _hdiutil_mount(mntpnt, image):
    """Context manager to mount osx dmg images and ensure they are
    unmounted on exit.
    """
    check_call(['hdiutil', 'attach', '-mountpoint', mntpnt, image])
    yield mntpnt
    check_call(['hdiutil', 'detach', mntpnt])


class OsxExtractor(Extractor):
    """The osx extractor
    """

    def copy(self, pkg_name):
        self.copy_files(pkg_name,
                        cuda_lib_dir=self.store,
                        nvvm_lib_dir=self.store,
                        libdevice_lib_dir=self.store)

    def _extract_matcher(self, tarmembers):
        """matcher helper for tarfile.extractall()
        """
        for tarinfo in tarmembers:
            ext = os.path.splitext(tarinfo.name)[-1]
            if ext == '.dylib' or ext == '.bc':
                yield tarinfo

    def _mount_extract(self, image, store):
        """Mounts and extracts the files from an image into store
        """
        with tempdir() as tmpmnt:
            with _hdiutil_mount(tmpmnt, os.path.join(os.getcwd(), image)) as mntpnt:
                for tlpath, tldirs, tlfiles in os.walk(mntpnt):
                    for tzfile in fnmatch.filter(tlfiles, "*.tar.gz"):
                        with tarfile.open(os.path.join(tlpath, tzfile)) as tar:
                            tar.extractall(
                                store, members=self._extract_matcher(tar))

    def extract(self, extract_dir):
        runfile = self.cu_blob
        patches = self.patches
        # fetch all the dylibs into lib64, but first get them out of the
        # image and tar.gzs into tmpstore
        extract_store_name = 'tmpstore'
        extract_store = os.path.join(extract_dir, extract_store_name)
        os.mkdir(extract_store)
        store_name = 'lib64'
        self.store = os.path.join(extract_dir, store_name)
        try:
            os.mkdir(self.store)
        except FileExistsError:
            pass
        self._mount_extract(runfile, extract_store)
        for p in self.patches:
            self._mount_extract(p, extract_store)
        for path, dirs, files in os.walk(extract_store):
            for filename in fnmatch.filter(files, "*.dylib"):
                if not Path(os.path.join(self.store, filename)).is_file():
                    shutil.copy(os.path.join(path, filename), self.store)
            for filename in fnmatch.filter(files, "*.bc"):
                if not Path(os.path.join(self.store, filename)).is_file():
                    shutil.copy(os.path.join(path, filename), self.store)


def getplatform():
    plt = sys.platform
    if plt.startswith('linux'):
        return 'linux'
    elif plt.startswith('win'):
        return 'windows'
    elif plt.startswith('darwin'):
        return 'osx'
    else:
        raise RuntimeError('Unknown platform')

dispatcher = {'linux': LinuxExtractor,
              'windows': WindowsExtractor,
              'osx': OsxExtractor}


def _main():
    print("Running build")

    # package version decl must match cuda release version
    cu_version = os.environ['PKG_VERSION']

    print("CUDA Version: {}".format(cu_version))

    # get an extractor
    plat = getplatform()
    extractor_impl = dispatcher[plat]
    version_cfg = config[cu_version]
    extractor = extractor_impl(cu_version, version_cfg, version_cfg[plat])

    # download binaries
    extractor.download_blobs()

    # check md5sum
    extractor.check_md5()
    try:
        os.mkdir("blob_files")
    except FileExistsError:
        pass

    # extract (just extracts libraries from distributed blob)
    extractor.extract("blob_files")

    pkg_name = os.environ['PKG_NAME']

    extractor.copy(pkg_name)

    extractor.make_link_scripts(pkg_name)

    # dump config
    # extractor.dump_config(pkg_name)

if __name__ == "__main__":
    _main()

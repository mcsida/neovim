%if 0%{?el8}
# see https://fedoraproject.org/wiki/Changes/CMake_to_do_out-of-source_builds
# EPEL 8's %%cmake defaults to in-source build, which neovim does not support
%undefine __cmake_in_source_build
%endif

%bcond_with jemalloc
%ifarch %{arm} %{ix86} x86_64 %{mips} s390x
  %bcond_without luajit
%else
  %ifarch aarch64
    %if 0%{?el8}
      # luajit codepath buggy on el8 aarch64
      # https://bugzilla.redhat.com/show_bug.cgi?id=2065340
      %bcond_with luajit
    %else
      %bcond_without luajit
    %endif
  %else
    %bcond_with luajit
  %endif
%endif

%if 0%{?el10}
# tree-sitter in EL10 is too old and libtree-sitter-devel is not shipped
# https://issues.redhat.com/browse/RHEL-56996
%bcond system_treesitter 0
%else
%bcond system_treesitter 1
%endif

%global luv_min_ver 1.43.0
%if %{with system_treesitter}
%global tree_sitter_min_ver 0.22.5
%endif
%global vterm_min_ver 0.3.3

%global luv_include_dir %{_includedir}/luv
%if %{with luajit}
%global luajit_version 2.1
%global lua_prg %{_bindir}/luajit
%else
%global lua_version 5.1
%global lua_prg %{_bindir}/lua-5.1
%endif

Name:           neovim
Version:        0.12.0
Release:        %autorelease

License:        Apache-2.0 AND Vim AND MIT
Summary:        Vim-fork focused on extensibility and agility
Url:            https://neovim.io

Source0:        https://github.com/neovim/neovim/archive/v%{version}/%{name}-%{version}.tar.gz
Source1:        sysinit.vim
Source2:        spec-template
Source3:        neovim-bundled-licenses.txt

Patch1000:      neovim-lua-bit32.patch

BuildRequires:  gcc-c++
BuildRequires:  cmake
BuildRequires:  desktop-file-utils
BuildRequires:  fdupes
BuildRequires:  gettext
BuildRequires:  gperf
BuildRequires:  gcc
BuildRequires:  libluv-devel >= %{luv_min_ver}
%if %{with luajit}
# luajit implements version 5.1 of the lua language spec, so it needs the
# compat versions of libs.
BuildRequires:  luajit-devel
Requires:       luajit2.1-luv >= %{luv_min_ver}
%else
# lua5.1
BuildRequires:  compat-lua
BuildRequires:  compat-lua-devel
BuildRequires:  lua5.1-bit32
Requires:       lua5.1-luv >= %{luv_min_ver}
# /with luajit
%endif
Requires:       lua5.1-lpeg >= 1.1.0
BuildRequires:  lua5.1-lpeg >= 1.1.0
BuildRequires:  lua5.1-mpack >= 1.0.11
%if %{with jemalloc}
BuildRequires:  jemalloc-devel
%endif
BuildRequires:  msgpack-devel >= 3.1.0
BuildRequires:  pkgconfig(termkey)
BuildRequires:  pkgconfig(libuv) >= 1.50.0
BuildRequires:  pkgconfig(vterm) >= %{vterm_min_ver}
# need the build with the fix for the resize buffer issue
Requires:       libvterm >= %{vterm_min_ver}
BuildRequires:  pkgconfig(unibilium)
BuildRequires:  pkgconfig(libutf8proc) >= 2.10.0
%if %{with system_treesitter}
BuildRequires:  pkgconfig(tree-sitter) >= %{tree_sitter_min_ver}
# tree-sitter didn't do an soname bump. enforce the min version
# see https://github.com/nvim-treesitter/nvim-treesitter/pull/3055/files
Requires:       libtree-sitter >= %{tree_sitter_min_ver}
%endif
# Parser generator, only needed for :TSInstallFromGrammar
Recommends:     tree-sitter-cli
Suggests:       (python2-neovim if python2)
Suggests:       (python3-neovim if python3)
# XSel provides access to the system clipboard
Recommends:     xsel
Recommends:     wl-clipboard
Recommends:     ripgrep
Recommends:     inotify-tools

%description
Neovim is a refactor - and sometimes redactor - in the tradition of
Vim, which itself derives from Stevie. It is not a rewrite, but a
continuation and extension of Vim. Many rewrites, clones, emulators
and imitators exist; some are very clever, but none are Vim. Neovim
strives to be a superset of Vim, notwithstanding some intentionally
removed misfeatures; excepting those few and carefully-considered
excisions, Neovim is Vim. It is built for users who want the good
parts of Vim, without compromise, and more.

%prep
%if %{with system_treesitter}
%setup -q -b3
%else
%setup -q -b3 -b5

mv ../%{name}-%{version}-vendor-treesitter/* \
  ../%{name}-%{version}-vendor/
%endif

cp %{SOURCE3} .

%if %{without luajit}
%patch -P 1000 -p1
%endif

%build
# set vars to make build reproducible; see config/CMakeLists.txt
HOSTNAME=koji
USERNAME=koji

 # Build the tree-sitter parsers first
mkdir -p .deps/build/
ln -sfr ../%{name}-%{version}-vendor .deps/build/downloads
%define _vpath_srcdir cmake.deps
%define __cmake_builddir .deps
%cmake -DCMAKE_BUILD_TYPE=RelWithDebInfo \
       -DUSE_BUNDLED=OFF \
%if %{without system_treesitter}
       -DUSE_BUNDLED_TS=ON \
%endif
       -DUSE_BUNDLED_TS_PARSERS=ON
%cmake_build

# Build neovim
%define _vpath_srcdir .
%define __cmake_builddir redhat-linux-build
%cmake -DCMAKE_BUILD_TYPE=RelWithDebInfo \
       -DPREFER_LUA=%{?with_luajit:OFF}%{!?with_luajit:ON} \
       -DLUA_PRG=%{lua_prg} \
       -DENABLE_JEMALLOC=%{?with_jemalloc:ON}%{!?with_jemalloc:OFF} \
       -DLIBLUV_INCLUDE_DIR:PATH=%{luv_include_dir} \
       -DENABLE_TRANSLATIONS=ON
%cmake_build

%install
%cmake_install

install -p -m 644 %{SOURCE1} %{buildroot}%{_datadir}/nvim/sysinit.vim
install -p -m 644 %{SOURCE2} %{buildroot}%{_datadir}/nvim/template.spec

desktop-file-install --dir=%{buildroot}%{_datadir}/applications \
    runtime/nvim.desktop
install -d -m0755 %{buildroot}%{_datadir}/pixmaps
install -m0644 runtime/nvim.png %{buildroot}%{_datadir}/pixmaps/nvim.png

%fdupes %{buildroot}%{_datadir}/
# Fix exec bits
find %{buildroot}%{_datadir} \( -name "*.bat" -o -name "*.awk" \) \
    -print -exec chmod -x '{}' \;
%find_lang nvim

# Refresh documentation helptags.
%transfiletriggerin -- %{_datadir}/nvim/runtime/doc
%{_bindir}/nvim -u NONE -es -c ":helptags %{_datadir}/nvim/runtime/doc" -c ":q" &> /dev/null || :

%transfiletriggerpostun -- %{_datadir}/nvim/runtime/doc
> %{_datadir}/nvim/runtime/doc/tags || :
%{_bindir}/nvim -u NONE -es -c ":helptags %{_datadir}/nvim/runtime/doc" -c ":q" &> /dev/null || :

%files -f nvim.lang
%license LICENSE.txt neovim-bundled-licenses.txt
%doc CONTRIBUTING.md MAINTAIN.md README.md
%{_bindir}/nvim

%dir %{_libdir}/nvim
%dir %{_libdir}/nvim/parser
%{_libdir}/nvim/parser/*.so

%{_mandir}/man1/nvim.1*
%{_datadir}/applications/nvim.desktop
%{_datadir}/pixmaps/nvim.png
%{_datadir}/icons/hicolor/128x128/apps/nvim.png

%dir %{_datadir}/nvim
%{_datadir}/nvim/sysinit.vim
%{_datadir}/nvim/template.spec

%dir %{_datadir}/nvim/runtime
%{_datadir}/nvim/runtime/*.vim
%{_datadir}/nvim/runtime/filetype.lua
%{_datadir}/nvim/runtime/neovim.ico

%dir %{_datadir}/nvim/runtime/autoload
%{_datadir}/nvim/runtime/autoload/README.txt
%{_datadir}/nvim/runtime/autoload/*.lua
%{_datadir}/nvim/runtime/autoload/*.vim

%dir %{_datadir}/nvim/runtime/autoload/cargo
%{_datadir}/nvim/runtime/autoload/cargo/*.vim

%dir %{_datadir}/nvim/runtime/autoload/dist
%{_datadir}/nvim/runtime/autoload/dist/*.vim

%dir %{_datadir}/nvim/runtime/autoload/provider
%{_datadir}/nvim/runtime/autoload/provider/*.vim
%{_datadir}/nvim/runtime/autoload/provider/script_host.rb

%dir %{_datadir}/nvim/runtime/autoload/remote
%{_datadir}/nvim/runtime/autoload/remote/*.vim

%dir %{_datadir}/nvim/runtime/autoload/rust
%{_datadir}/nvim/runtime/autoload/rust/*.vim

%dir %{_datadir}/nvim/runtime/autoload/xml
%{_datadir}/nvim/runtime/autoload/xml/*.vim

%dir %{_datadir}/nvim/runtime/colors
%{_datadir}/nvim/runtime/colors/*.lua
%{_datadir}/nvim/runtime/colors/*.vim
%{_datadir}/nvim/runtime/colors/README.txt

%dir %{_datadir}/nvim/runtime/compiler
%{_datadir}/nvim/runtime/compiler/*.vim
%{_datadir}/nvim/runtime/compiler/README.txt

%dir %{_datadir}/nvim/runtime/doc
%{_datadir}/nvim/runtime/doc/*.txt
%{_datadir}/nvim/runtime/doc/tags

%dir %{_datadir}/nvim/runtime/ftplugin
%{_datadir}/nvim/runtime/ftplugin/*.vim
%{_datadir}/nvim/runtime/ftplugin/*.lua
%{_datadir}/nvim/runtime/ftplugin/logtalk.dict
%{_datadir}/nvim/runtime/ftplugin/README.txt

%dir %{_datadir}/nvim/runtime/indent
%{_datadir}/nvim/runtime/indent/Makefile
%{_datadir}/nvim/runtime/indent/README.txt
%{_datadir}/nvim/runtime/indent/*.lua
%{_datadir}/nvim/runtime/indent/*.vim

%dir %{_datadir}/nvim/runtime/indent/testdir/
%{_datadir}/nvim/runtime/indent/testdir/README.txt
%{_datadir}/nvim/runtime/indent/testdir/*.in
%{_datadir}/nvim/runtime/indent/testdir/*.ok
%{_datadir}/nvim/runtime/indent/testdir/*.vim

%dir %{_datadir}/nvim/runtime/keymap
%{_datadir}/nvim/runtime/keymap/*.vim
%{_datadir}/nvim/runtime/keymap/README.txt

%dir %{_datadir}/nvim/runtime/lua
%{_datadir}/nvim/runtime/lua/*.lua

%dir %{_datadir}/nvim/runtime/lua/vim
%{_datadir}/nvim/runtime/lua/vim/*.lua

%dir %{_datadir}/nvim/runtime/lua/vim/_ftplugin
%{_datadir}/nvim/runtime/lua/vim/_ftplugin/*.lua

%dir %{_datadir}/nvim/runtime/lua/vim/_meta
%{_datadir}/nvim/runtime/lua/vim/_meta/*.lua

%dir %{_datadir}/nvim/runtime/lua/vim/deprecated
%{_datadir}/nvim/runtime/lua/vim/deprecated/health.lua

%dir %{_datadir}/nvim/runtime/lua/vim/filetype
%{_datadir}/nvim/runtime/lua/vim/filetype/*.lua

%dir %{_datadir}/nvim/runtime/lua/vim/health
%{_datadir}/nvim/runtime/lua/vim/health/*.lua

%dir %{_datadir}/nvim/runtime/lua/vim/func
%{_datadir}/nvim/runtime/lua/vim/func/*.lua

%dir %{_datadir}/nvim/runtime/lua/vim/lsp
%{_datadir}/nvim/runtime/lua/vim/lsp/*.lua

%dir %{_datadir}/nvim/runtime/lua/vim/lsp/_meta
%{_datadir}/nvim/runtime/lua/vim/lsp/_meta/*.lua

%dir %{_datadir}/nvim/runtime/lua/vim/provider
%{_datadir}/nvim/runtime/lua/vim/provider/*.lua

%dir %{_datadir}/nvim/runtime/lua/vim/treesitter
%{_datadir}/nvim/runtime/lua/vim/treesitter/*.lua

%dir %{_datadir}/nvim/runtime/lua/vim/treesitter/_meta
%{_datadir}/nvim/runtime/lua/vim/treesitter/_meta/*.lua

%dir %{_datadir}/nvim/runtime/lua/vim/ui
%dir %{_datadir}/nvim/runtime/lua/vim/ui/clipboard
%{_datadir}/nvim/runtime/lua/vim/ui/clipboard/*.lua

%dir %{_datadir}/nvim/runtime/pack
%dir %{_datadir}/nvim/runtime/pack/dist
%dir %{_datadir}/nvim/runtime/pack/dist/opt

%dir %{_datadir}/nvim/runtime/pack/dist/opt/cfilter
%dir %{_datadir}/nvim/runtime/pack/dist/opt/cfilter/plugin
%{_datadir}/nvim/runtime/pack/dist/opt/cfilter/plugin/*.lua

%dir %{_datadir}/nvim/runtime/pack/dist/opt/justify
%dir %{_datadir}/nvim/runtime/pack/dist/opt/justify/plugin
%{_datadir}/nvim/runtime/pack/dist/opt/justify/plugin/*.vim

%dir %{_datadir}/nvim/runtime/pack/dist/opt/netrw
%{_datadir}/nvim/runtime/pack/dist/opt/netrw/LICENSE.txt
%{_datadir}/nvim/runtime/pack/dist/opt/netrw/README.md

%dir %{_datadir}/nvim/runtime/pack/dist/opt/netrw/autoload
%{_datadir}/nvim/runtime/pack/dist/opt/netrw/autoload/*.vim

%dir %{_datadir}/nvim/runtime/pack/dist/opt/netrw/doc
%{_datadir}/nvim/runtime/pack/dist/opt/netrw/doc/*.txt
%{_datadir}/nvim/runtime/pack/dist/opt/netrw/doc/tags

%dir %{_datadir}/nvim/runtime/pack/dist/opt/netrw/plugin
%{_datadir}/nvim/runtime/pack/dist/opt/netrw/plugin/*.vim

%dir %{_datadir}/nvim/runtime/pack/dist/opt/netrw/syntax
%{_datadir}/nvim/runtime/pack/dist/opt/netrw/syntax/*.vim

%dir %{_datadir}/nvim/runtime/pack/dist/opt/nohlsearch

%dir %{_datadir}/nvim/runtime/pack/dist/opt/nohlsearch/plugin
%{_datadir}/nvim/runtime/pack/dist/opt/nohlsearch/plugin/*.vim

%dir %{_datadir}/nvim/runtime/pack/dist/opt/shellmenu
%dir %{_datadir}/nvim/runtime/pack/dist/opt/shellmenu/plugin
%{_datadir}/nvim/runtime/pack/dist/opt/shellmenu/plugin/*.vim

%dir %{_datadir}/nvim/runtime/pack/dist/opt/matchit
%dir %{_datadir}/nvim/runtime/pack/dist/opt/matchit/autoload
%{_datadir}/nvim/runtime/pack/dist/opt/matchit/autoload/*.vim
%dir %{_datadir}/nvim/runtime/pack/dist/opt/matchit/doc
%{_datadir}/nvim/runtime/pack/dist/opt/matchit/doc/matchit.txt
%{_datadir}/nvim/runtime/pack/dist/opt/matchit/doc/tags
%dir %{_datadir}/nvim/runtime/pack/dist/opt/matchit/plugin
%{_datadir}/nvim/runtime/pack/dist/opt/matchit/plugin/*.vim

%dir %{_datadir}/nvim/runtime/pack/dist/opt/swapmouse
%dir %{_datadir}/nvim/runtime/pack/dist/opt/swapmouse/plugin
%{_datadir}/nvim/runtime/pack/dist/opt/swapmouse/plugin/*.vim

%dir %{_datadir}/nvim/runtime/pack/dist/opt/termdebug
%dir %{_datadir}/nvim/runtime/pack/dist/opt/termdebug/plugin
%{_datadir}/nvim/runtime/pack/dist/opt/termdebug/plugin/*.vim

%dir %{_datadir}/nvim/runtime/plugin
%{_datadir}/nvim/runtime/plugin/*.lua
%{_datadir}/nvim/runtime/plugin/*.vim

%dir %{_datadir}/nvim/runtime/queries/

%dir %{_datadir}/nvim/runtime/queries/c
%{_datadir}/nvim/runtime/queries/c/*.scm

%dir %{_datadir}/nvim/runtime/queries/lua/
%{_datadir}/nvim/runtime/queries/lua/folds.scm
%{_datadir}/nvim/runtime/queries/lua/highlights.scm
%{_datadir}/nvim/runtime/queries/lua/injections.scm

%dir %{_datadir}/nvim/runtime/queries/markdown
%{_datadir}/nvim/runtime/queries/markdown/*.scm

%dir %{_datadir}/nvim/runtime/queries/markdown_inline
%{_datadir}/nvim/runtime/queries/markdown_inline/*.scm

%dir %{_datadir}/nvim/runtime/queries/query
%{_datadir}/nvim/runtime/queries/query/*.scm

%dir %{_datadir}/nvim/runtime/queries/vim/
%{_datadir}/nvim/runtime/queries/vim/*.scm

%dir %{_datadir}/nvim/runtime/queries/vimdoc/
%{_datadir}/nvim/runtime/queries/vimdoc/*.scm

%dir %{_datadir}/nvim/runtime/scripts
%{_datadir}/nvim/runtime/scripts/*.lua
%{_datadir}/nvim/runtime/scripts/*.vim
%{_datadir}/nvim/runtime/scripts/less.bat
%{_datadir}/nvim/runtime/scripts/less.sh

%dir %{_datadir}/nvim/runtime/spell
%{_datadir}/nvim/runtime/spell/cleanadd.vim
%{_datadir}/nvim/runtime/spell/en.utf-8.spl

%dir %{_datadir}/nvim/runtime/syntax
%{_datadir}/nvim/runtime/syntax/*.lua
%{_datadir}/nvim/runtime/syntax/*.vim
%{_datadir}/nvim/runtime/syntax/README.txt

%dir %{_datadir}/nvim/runtime/syntax/modula2
%dir %{_datadir}/nvim/runtime/syntax/modula2/opt
%{_datadir}/nvim/runtime/syntax/modula2/opt/*.vim

%dir %{_datadir}/nvim/runtime/syntax/vim
%{_datadir}/nvim/runtime/syntax/vim/generated.vim

%dir %{_datadir}/nvim/runtime/syntax/shared
%{_datadir}/nvim/runtime/syntax/shared/*.vim
%{_datadir}/nvim/runtime/syntax/shared/README.txt

%dir %{_datadir}/nvim/runtime/tutor
%{_datadir}/nvim/runtime/tutor/tutor.tutor
%{_datadir}/nvim/runtime/tutor/tutor.tutor.json

%dir %{_datadir}/nvim/runtime/tutor/en
%{_datadir}/nvim/runtime/tutor/en/vim-01-beginner.tutor
%{_datadir}/nvim/runtime/tutor/en/vim-01-beginner.tutor.json

%dir %{_datadir}/nvim/runtime/tutor/ja
%{_datadir}/nvim/runtime/tutor/ja/vim-01-beginner.tutor
%{_datadir}/nvim/runtime/tutor/ja/vim-01-beginner.tutor.json

%changelog
%autochangelog


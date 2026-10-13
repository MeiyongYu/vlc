# qtshadertools
# required for Qt5Compat, and for qtdeclarative.

QTSHADERTOOLS_VERSION := $(QTBASE_VERSION)
QTSHADERTOOLS_URL := $(QT)/$(QTSHADERTOOLS_VERSION)/submodules/qtshadertools-everywhere-src-$(QTSHADERTOOLS_VERSION).tar.xz

DEPS_qtshadertools-tools = qt-tools $(DEPS_qt-tools)

ifdef HAVE_WIN32
DEPS_qtshadertools-tools += fxc2 $(DEPS_fxc2)
endif

ifneq ($(findstring qt,$(PKGS)),)
PKGS_TOOLS += qtshadertools-tools
endif
PKGS_ALL += qtshadertools-tools

ifdef QT_USES_SYSTEM_TOOLS
PKGS_FOUND += qtshadertools-tools
endif

$(TARBALLS)/qtshadertools-everywhere-src-$(QTSHADERTOOLS_VERSION).tar.xz:
	$(call download_pkg,$(QTSHADERTOOLS_URL),qtshadertools)

.sum-qtshadertools: qtshadertools-everywhere-src-$(QTSHADERTOOLS_VERSION).tar.xz

.sum-qtshadertools-tools: .sum-qtshadertools
	touch $@

ifdef HAVE_CROSS_COMPILE
QT_SHADETOOLS_NATIVE_CONFIG := -DCMAKE_TOOLCHAIN_FILE=$(QT_HOST_LIBS)/cmake/Qt6/qt.toolchain.cmake
else
QT_SHADETOOLS_NATIVE_CONFIG := $(QT_CMAKE_CONFIG)
endif

qtshadertools: qtshadertools-everywhere-src-$(QTSHADERTOOLS_VERSION).tar.xz .sum-qtshadertools
	$(UNPACK)
	$(MOVE)

.qtshadertools-tools: BUILD_DIR=$</vlc_native
.qtshadertools-tools: qtshadertools
	# Force Qt6::Gui target creation so qsb (which needs Qt6Gui) is not skipped.
	# QT_HOST_PATH is baked into the Qt install config, so Qt treats this native
	# build as a (fake) cross build and sets QT_NO_CREATE_TARGETS=TRUE, which
	# prevents the Qt6::Gui target from being created -> the whole repo is skipped.
	sed -i '0,/^find_package(Qt6/ s//set(QT_NO_CREATE_TARGETS FALSE)\n&/' $</CMakeLists.txt
	$(CMAKECLEAN)
	# Do NOT use any toolchain file here: a toolchain forces CMAKE_CROSSCOMPILING=TRUE,
	# which in Qt's tool helper logic makes qsb a "host tool" that must already exist
	# instead of being built from source. With no toolchain, CMAKE_CROSSCOMPILING=FALSE
	# and -DQT_FORCE_BUILD_TOOLS:BOOL=ON builds qsb from source.
	# CMAKE_PREFIX_PATH/FIND_ROOT_PATH + PNG_ROOT/FREETYPE_DIR let FindPNG/FindFreetype
	# locate the contrib-built libraries so Qt6Gui is found.
	$(BUILDVARS) cmake -S $< -B $(BUILD_DIR) \
		-DCMAKE_POSITION_INDEPENDENT_CODE=ON \
		-DBUILD_SHARED_LIBS:BOOL=OFF \
		-DCMAKE_INSTALL_LIBDIR:STRING=lib \
		-DBUILD_TESTING:BOOL=OFF \
		-G $(CMAKE_GENERATOR) \
		-DCMAKE_INSTALL_PREFIX:STRING=$(BUILDPREFIX) \
		-DCMAKE_PREFIX_PATH=$(PREFIX) \
		-DCMAKE_FIND_ROOT_PATH=$(PREFIX) \
		-DPNG_ROOT=$(PREFIX) \
		-DFREETYPE_DIR=$(PREFIX) \
		-DQT_HOST_PATH=$(BUILDPREFIX) \
		-DQT_FORCE_BUILD_TOOLS:BOOL=ON \
		--log-level=STATUS
	$(CMAKEBUILD)
	$(CMAKEINSTALL)
	touch $@

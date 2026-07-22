#
# Copyright (C) 2022  Autodesk, Inc. All Rights Reserved.
#
# SPDX-License-Identifier: Apache-2.0
#

SET(_target
    "session_manager"
)

FILE(GLOB_RECURSE _pkg_files
     RELATIVE ${CMAKE_CURRENT_SOURCE_DIR}
     CONFIGURE_DEPENDS *
)
LIST(FILTER _pkg_files EXCLUDE REGEX "\\.mu\\.in$")
LIST(FILTER _pkg_files EXCLUDE REGEX "\\.mu$")
LIST(FILTER _pkg_files EXCLUDE REGEX "__pycache__")
LIST(FILTER _pkg_files EXCLUDE REGEX "\\.pyc$")
LIST(FILTER _pkg_files EXCLUDE REGEX "\\.pyo$")
LIST(APPEND _pkg_files session_manager_api.mu)
LIST(REMOVE_ITEM _pkg_files Makefile CMakeLists.txt PACKAGE)

RV_STAGE(TYPE "RVPKG" TARGET ${_target} FILES ${_pkg_files})

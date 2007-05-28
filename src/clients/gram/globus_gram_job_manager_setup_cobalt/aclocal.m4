dnl aclocal.m4 generated automatically by aclocal 1.4

dnl Copyright (C) 1994, 1995-8, 1999 Free Software Foundation, Inc.
dnl This file is free software; the Free Software Foundation
dnl gives unlimited permission to copy and/or distribute it,
dnl with or without modifications, as long as this notice is preserved.

dnl This program is distributed in the hope that it will be useful,
dnl but WITHOUT ANY WARRANTY, to the extent permitted by law; without
dnl even the implied warranty of MERCHANTABILITY or FITNESS FOR A
dnl PARTICULAR PURPOSE.

AC_DEFUN(GLOBUS_INIT, [

AM_MAINTAINER_MODE

# checking for the GLOBUS_LOCATION

if test "x$GLOBUS_LOCATION" = "x"; then
    echo "ERROR Please specify GLOBUS_LOCATION" >&2
    exit 1
fi
if test "x$GPT_LOCATION" = "x"; then
    GPT_LOCATION=$GLOBUS_LOCATION
    export GPT_LOCATION
fi

#extract whether the package is built with flavors from the src metadata
$GPT_LOCATION/sbin/gpt_extract_data --build $srcdir/pkgdata/pkg_data_src.gpt.in > tmpfile.gpt

. ./tmpfile.gpt
rm ./tmpfile.gpt

if test "x$GPT_BUILD_WITH_FLAVORS" = "xno"; then
        GLOBUS_FLAVOR_NAME="noflavor"
fi

AC_ARG_WITH(flavor,
	[ --with-flavor=<FL>     Specify the globus build flavor or without-flavor for a flavor independent  ],

	[
	case $withval in
	no)
		NO_FLAVOR="yes"
		;;
	yes)
		echo "Please specify a globus build flavor" >&2
		exit 1
		;;
	*)
        if test "x$GLOBUS_FLAVOR_NAME" = "xnoflavor"; then
	        echo "Warning: package doesn't build with flavors $withval ignored" >&2
	        echo "Warning: $withval ignored" >&2
        else
		GLOBUS_FLAVOR_NAME=$withval
                if test ! -f "$GLOBUS_LOCATION/etc/globus_core/flavor_$GLOBUS_FLAVOR_NAME.gpt"; then
	                echo "ERROR: Flavor $GLOBUS_FLAVOR_NAME has not been installed" >&2
	                exit 1
                fi 

        fi
		;;
	esac
	],

	[ 
        if test "x$GLOBUS_FLAVOR_NAME" = "x"; then
	        echo "Please specify a globus build flavor" >&2
	        exit 1
        fi
	]
)


GPT_INIT



AM_CONDITIONAL(WITHOUT_FLAVORS, test "$NO_FLAVOR" = "yes")
AC_SUBST(GLOBUS_FLAVOR_NAME)


# get the environment scripts

if test "x$GLOBUS_FLAVOR_NAME" != "xnoflavor" ; then
	. $GLOBUS_LOCATION/libexec/globus-build-env-$GLOBUS_FLAVOR_NAME.sh
fi

prefix='$(GLOBUS_LOCATION)'
exec_prefix='$(GLOBUS_LOCATION)'

AC_SUBST(CC)
AC_SUBST(CPP)
AC_SUBST(CFLAGS)
AC_SUBST(CPPFLAGS)
AC_SUBST(LD)
AC_SUBST(LDFLAGS)
AC_SUBST(LIBS)
AC_SUBST(CXX)
AC_SUBST(CXXCPP)
AC_SUBST(CXXFLAGS)
AC_SUBST(INSURE)
AC_SUBST(DOXYGEN)
AC_SUBST(F77)
AC_SUBST(F77FLAGS)
AC_SUBST(F90)
AC_SUBST(F90FLAGS)
AC_SUBST(AR)
AC_SUBST(ARFLAGS)
AC_SUBST(RANLIB)
AC_SUBST(PERL)
AC_SUBST(CROSS)
AC_SUBST(cross_compiling)
AC_SUBST(OBJEXT)
AC_SUBST(EXEEXT)


define([AM_PROG_LIBTOOL],[
	LIBTOOL='$(SHELL) $(GLOBUS_LOCATION)/sbin/libtool-$(GLOBUS_FLAVOR_NAME)'
	AC_SUBST(LIBTOOL)
	AC_SUBST(LN_S)
])

dnl define FILELIST_FILE variable
FILELIST_FILE=`pwd`;
FILELIST_FILE="$FILELIST_FILE/pkgdata/master.filelist"
AC_SUBST(FILELIST_FILE)

dnl export version information
dnl branch id 99999 means that timestamp refers to build time
if test -f $srcdir/dirt.sh ; then
    . $srcdir/dirt.sh
else
    DIRT_TIMESTAMP=`perl -e 'print time'`
    DIRT_BRANCH_ID=99999
fi

dnl GPT_MAJOR_VERSION and GPT_MINOR_VERSION provided by GPT_INIT
AC_SUBST(GPT_MAJOR_VERSION)
AC_SUBST(GPT_MINOR_VERSION)
AC_SUBST(DIRT_TIMESTAMP)
AC_SUBST(DIRT_BRANCH_ID)



dnl END OF GLOBUS_INIT
])


AC_DEFUN(GLOBUS_FINALIZE, [

lac_INSURE=$INSURE

AC_ARG_ENABLE(insure,
 	changequote(<<, >>)dnl
  <<--disable-insure	disable Insure++ >>,
	changequote([, ])dnl
	[
		if test "$enableval" = "yes"; then
			lac_INSURE="${INSURE-insure}"
		else
			lac_INSURE="$enableval"
		fi
	],
	[
		lac_INSURE=""
	])


if test ! -z "$lac_INSURE"; then
	CC=$lac_INSURE
	LD=$lac_INSURE
	CXX=$lac_INSURE
	AC_SUBST(CC) 
	AC_SUBST(LD) 
	AC_SUBST(CXX) 
fi 

])


# Add --enable-maintainer-mode option to configure.
# From Jim Meyering

# serial 1

AC_DEFUN(AM_MAINTAINER_MODE,
[AC_MSG_CHECKING([whether to enable maintainer-specific portions of Makefiles])
  dnl maintainer-mode is disabled by default
  AC_ARG_ENABLE(maintainer-mode,
[  --enable-maintainer-mode enable make rules and dependencies not useful
                          (and sometimes confusing) to the casual installer],
      USE_MAINTAINER_MODE=$enableval,
      USE_MAINTAINER_MODE=no)
  AC_MSG_RESULT($USE_MAINTAINER_MODE)
  AM_CONDITIONAL(MAINTAINER_MODE, test $USE_MAINTAINER_MODE = yes)
  MAINT=$MAINTAINER_MODE_TRUE
  AC_SUBST(MAINT)dnl
]
)

# Define a conditional.

AC_DEFUN(AM_CONDITIONAL,
[AC_SUBST($1_TRUE)
AC_SUBST($1_FALSE)
if $2; then
  $1_TRUE=
  $1_FALSE='#'
else
  $1_TRUE='#'
  $1_FALSE=
fi])

dnl GPT_INIT()
AC_DEFUN(GPT_INIT, [
        if test "x$GPT_LOCATION" = "x"; then
                echo "ERROR Please specify GPT_LOCATION" >&2
                exit 1
        fi

        AC_SUBST(GPT_LOCATION)

	#extract the name and version of the package from the src metadata
	$GPT_LOCATION/sbin/gpt_extract_data --name --version $srcdir/pkgdata/pkg_data_src.gpt.in > tmpfile.gpt
	. ./tmpfile.gpt
	rm ./tmpfile.gpt
	GPT_VERSION="$GPT_MAJOR_VERSION.$GPT_MINOR_VERSION"

        # Determine if GPT is version 2.x

        GPT_IS_2="no"

        if test -f "$GPT_LOCATION/sbin/gpt-build"; then
                GPT_IS_2="yes"
        fi

        AC_SUBST(GPT_IS_2)

	#Default to shared, before checking static-only
	GPT_LINKTYPE="shared"
	# We have to figure out if we're linking only static before build_config
	AC_ARG_ENABLE(static-only,
	[ --enable-static-only     Don't do any dynamic linking],

	[
	case $enableval in
	no)
		GPT_LINKTYPE="shared"
		;;
	yes)
		GPT_LINKTYPE="static"
dnl		if test "$STATIC_LDFLAGS" = ""; then
dnl		GPT_LDFLAGS=" -all-static $GPT_LDFLAGS"
dnl		else
dnl		GPT_LDFLAGS=" $STATIC_LDFLAGS $GPT_LDFLAGS"
dnl		fi
		;;
	*)
		echo "--enable-static-only has no arguments" >&2
		exit 1
		;;
	esac
	]
	)

	#extract the cumulative build environment from the installed development tree
	[
	if $GPT_LOCATION/sbin/gpt_build_config -src $srcdir/pkgdata/pkg_data_src.gpt.in -f $GLOBUS_FLAVOR_NAME -link $GPT_LINKTYPE; then 
		echo "Dependencies Complete";
	else 
		exit 1;
	fi
	]

# The following variables are used to manage the build enviroment
# GPT_CFLAGS, GPT_INCLUDES, GPT_PGM_LINKS, GPT_LIB_LINKS, and GPT_LDFLAGS
# are the variables used in the Makefile.am's
# GPT_PKG_CFLAGS, GPT_EXTERNAL_INCLUDES and GPT_EXTERNAL_LIBS are stored 
# as build data in the packaging metadata file.
# GPT_CONFIG_FLAGS, GPT_CONFIG_INCLUDES, GPT_CONFIG_PGM_LINKS, and 
# GPT_CONFIG_LIB_LINKS are returned by gpt_build_config and contain build
# environment data from the dependent packages.



	. ./gpt_build_temp.sh  
	rm ./gpt_build_temp.sh
	GPT_CFLAGS="$GPT_CONFIG_CFLAGS"
	GPT_INCLUDES="-I$GLOBUS_LOCATION/include/$GLOBUS_FLAVOR_NAME $GPT_CONFIG_INCLUDES"
	GPT_LIBS="$GPT_CONFIG_PKG_LIBS $GPT_CONFIG_LIBS"
	GPT_LDFLAGS="$GPT_CONFIG_STATIC_LINKLINE -L$GLOBUS_LOCATION/lib $GPT_LDFLAGS"
	GPT_PGM_LINKS="$GPT_CONFIG_PGM_LINKS $GPT_CONFIG_LIBS"
	GPT_LIB_LINKS="$GPT_CONFIG_LIB_LINKS $GPT_CONFIG_LIBS"



	AC_SUBST(GPT_CFLAGS)
	AC_SUBST(GPT_PKG_CFLAGS)
	AC_SUBST(GPT_INCLUDES)
	AC_SUBST(GPT_EXTERNAL_INCLUDES)
	AC_SUBST(GPT_EXTERNAL_LIBS)
	AC_SUBST(GPT_LIBS)
	AC_SUBST(GPT_LDFLAGS)
	AC_SUBST(GPT_CONFIG_CFLAGS)
	AC_SUBST(GPT_CONFIG_INCLUDES)
	AC_SUBST(GPT_CONFIG_LIBS)
	AC_SUBST(GPT_CONFIG_PKG_LIBS)
	AC_SUBST(GPT_PGM_LINKS)
	AC_SUBST(GPT_LIB_LINKS)
	AC_SUBST(GPT_LINKTYPE)
	builddir=`pwd`
	AC_SUBST(builddir)
])

AC_DEFUN(GPT_SET_CFLAGS, [
	GPT_CFLAGS_TMP=$1
	GPT_CFLAGS="$GPT_CFLAGS_TMP $GPT_CFLAGS"
	GPT_PKG_CFLAGS="$GPT_CFLAGS_TMP $GPT_PKG_CFLAGS"
])

AC_DEFUN(GPT_SET_INCLUDES, [

	GPT_INCLUDES_TMP=$1
	GPT_EXTERNAL_INCLUDES="$GPT_EXTERNAL_INCLUDES $GPT_INCLUDES_TMP"
	GPT_INCLUDES="$GPT_INCLUDES_TMP $GPT_INCLUDES"
])

AC_DEFUN(GPT_SET_LIBS, [

	GPT_LIBS_TMP=$1
	GPT_EXTERNAL_LIBS="$GPT_EXTERNAL_LIBS $GPT_LIBS_TMP"
	GPT_LIB_LINKS=" $GPT_LIB_LINKS $GPT_LIBS_TMP"
	GPT_PGM_LINKS=" $GPT_PGM_LINKS $GPT_LIBS_TMP"
])

AC_DEFUN(GPT_SET_LDFLAGS, [
 
         GPT_LDFLAGS_TMP=$1
	 GPT_EXTERNAL_LDFLAGS="$GPT_EXTERNAL_LDFLAGS $GPT_LDFLAGS_TMP"
	 GPT_LDFLAGS=" $GPT_LDFLAGS_TMP $GPT_LDFLAGS"
])


# serial 40 AC_PROG_LIBTOOL
AC_DEFUN(AC_PROG_LIBTOOL,
[AC_REQUIRE([AC_LIBTOOL_SETUP])dnl

# Save cache, so that ltconfig can load it
AC_CACHE_SAVE

# Actually configure libtool.  ac_aux_dir is where install-sh is found.
CC="$CC" CFLAGS="$CFLAGS" CPPFLAGS="$CPPFLAGS" \
LD="$LD" LDFLAGS="$LDFLAGS" LIBS="$LIBS" \
LN_S="$LN_S" NM="$NM" RANLIB="$RANLIB" \
DLLTOOL="$DLLTOOL" AS="$AS" OBJDUMP="$OBJDUMP" \
${CONFIG_SHELL-/bin/sh} $ac_aux_dir/ltconfig --no-reexec \
$libtool_flags --no-verify $ac_aux_dir/ltmain.sh $lt_target \
|| AC_MSG_ERROR([libtool configure failed])

# Reload cache, that may have been modified by ltconfig
AC_CACHE_LOAD

# This can be used to rebuild libtool when needed
LIBTOOL_DEPS="$ac_aux_dir/ltconfig $ac_aux_dir/ltmain.sh"

# Always use our own libtool.
LIBTOOL='$(SHELL) $(top_builddir)/libtool'
AC_SUBST(LIBTOOL)dnl

# Redirect the config.log output again, so that the ltconfig log is not
# clobbered by the next message.
exec 5>>./config.log
])

AC_DEFUN(AC_LIBTOOL_SETUP,
[AC_PREREQ(2.13)dnl
AC_REQUIRE([AC_ENABLE_SHARED])dnl
AC_REQUIRE([AC_ENABLE_STATIC])dnl
AC_REQUIRE([AC_ENABLE_FAST_INSTALL])dnl
AC_REQUIRE([AC_CANONICAL_HOST])dnl
AC_REQUIRE([AC_CANONICAL_BUILD])dnl
AC_REQUIRE([AC_PROG_RANLIB])dnl
AC_REQUIRE([AC_PROG_CC])dnl
AC_REQUIRE([AC_PROG_LD])dnl
AC_REQUIRE([AC_PROG_NM])dnl
AC_REQUIRE([AC_PROG_LN_S])dnl
dnl

case "$target" in
NONE) lt_target="$host" ;;
*) lt_target="$target" ;;
esac

# Check for any special flags to pass to ltconfig.
#
# the following will cause an existing older ltconfig to fail, so
# we ignore this at the expense of the cache file... Checking this 
# will just take longer ... bummer!
#libtool_flags="--cache-file=$cache_file"
#
test "$enable_shared" = no && libtool_flags="$libtool_flags --disable-shared"
test "$enable_static" = no && libtool_flags="$libtool_flags --disable-static"
test "$enable_fast_install" = no && libtool_flags="$libtool_flags --disable-fast-install"
test "$ac_cv_prog_gcc" = yes && libtool_flags="$libtool_flags --with-gcc"
test "$ac_cv_prog_gnu_ld" = yes && libtool_flags="$libtool_flags --with-gnu-ld"
ifdef([AC_PROVIDE_AC_LIBTOOL_DLOPEN],
[libtool_flags="$libtool_flags --enable-dlopen"])
ifdef([AC_PROVIDE_AC_LIBTOOL_WIN32_DLL],
[libtool_flags="$libtool_flags --enable-win32-dll"])
AC_ARG_ENABLE(libtool-lock,
  [  --disable-libtool-lock  avoid locking (might break parallel builds)])
test "x$enable_libtool_lock" = xno && libtool_flags="$libtool_flags --disable-lock"
test x"$silent" = xyes && libtool_flags="$libtool_flags --silent"

# Some flags need to be propagated to the compiler or linker for good
# libtool support.
case "$lt_target" in
*-*-irix6*)
  # Find out which ABI we are using.
  echo '[#]line __oline__ "configure"' > conftest.$ac_ext
  if AC_TRY_EVAL(ac_compile); then
    case "`/usr/bin/file conftest.o`" in
    *32-bit*)
      LD="${LD-ld} -32"
      ;;
    *N32*)
      LD="${LD-ld} -n32"
      ;;
    *64-bit*)
      LD="${LD-ld} -64"
      ;;
    esac
  fi
  rm -rf conftest*
  ;;

*-*-sco3.2v5*)
  # On SCO OpenServer 5, we need -belf to get full-featured binaries.
  SAVE_CFLAGS="$CFLAGS"
  CFLAGS="$CFLAGS -belf"
  AC_CACHE_CHECK([whether the C compiler needs -belf], lt_cv_cc_needs_belf,
    [AC_TRY_LINK([],[],[lt_cv_cc_needs_belf=yes],[lt_cv_cc_needs_belf=no])])
  if test x"$lt_cv_cc_needs_belf" != x"yes"; then
    # this is probably gcc 2.8.0, egcs 1.0 or newer; no need for -belf
    CFLAGS="$SAVE_CFLAGS"
  fi
  ;;

ifdef([AC_PROVIDE_AC_LIBTOOL_WIN32_DLL],
[*-*-cygwin* | *-*-mingw*)
  AC_CHECK_TOOL(DLLTOOL, dlltool, false)
  AC_CHECK_TOOL(AS, as, false)
  AC_CHECK_TOOL(OBJDUMP, objdump, false)
  ;;
])
esac
])

# AC_LIBTOOL_DLOPEN - enable checks for dlopen support
AC_DEFUN(AC_LIBTOOL_DLOPEN, [AC_BEFORE([$0],[AC_LIBTOOL_SETUP])])

# AC_LIBTOOL_WIN32_DLL - declare package support for building win32 dll's
AC_DEFUN(AC_LIBTOOL_WIN32_DLL, [AC_BEFORE([$0], [AC_LIBTOOL_SETUP])])

# AC_ENABLE_SHARED - implement the --enable-shared flag
# Usage: AC_ENABLE_SHARED[(DEFAULT)]
#   Where DEFAULT is either `yes' or `no'.  If omitted, it defaults to
#   `yes'.
AC_DEFUN(AC_ENABLE_SHARED, [dnl
define([AC_ENABLE_SHARED_DEFAULT], ifelse($1, no, no, yes))dnl
AC_ARG_ENABLE(shared,
changequote(<<, >>)dnl
<<  --enable-shared[=PKGS]  build shared libraries [default=>>AC_ENABLE_SHARED_DEFAULT],
changequote([, ])dnl
[p=${PACKAGE-default}
case "$enableval" in
yes) enable_shared=yes ;;
no) enable_shared=no ;;
*)
  enable_shared=no
  # Look at the argument we got.  We use all the common list separators.
  IFS="${IFS= 	}"; ac_save_ifs="$IFS"; IFS="${IFS}:,"
  for pkg in $enableval; do
    if test "X$pkg" = "X$p"; then
      enable_shared=yes
    fi
  done
  IFS="$ac_save_ifs"
  ;;
esac],
enable_shared=AC_ENABLE_SHARED_DEFAULT)dnl
])

# AC_DISABLE_SHARED - set the default shared flag to --disable-shared
AC_DEFUN(AC_DISABLE_SHARED, [AC_BEFORE([$0],[AC_LIBTOOL_SETUP])dnl
AC_ENABLE_SHARED(no)])

# AC_ENABLE_STATIC - implement the --enable-static flag
# Usage: AC_ENABLE_STATIC[(DEFAULT)]
#   Where DEFAULT is either `yes' or `no'.  If omitted, it defaults to
#   `yes'.
AC_DEFUN(AC_ENABLE_STATIC, [dnl
define([AC_ENABLE_STATIC_DEFAULT], ifelse($1, no, no, yes))dnl
AC_ARG_ENABLE(static,
changequote(<<, >>)dnl
<<  --enable-static[=PKGS]  build static libraries [default=>>AC_ENABLE_STATIC_DEFAULT],
changequote([, ])dnl
[p=${PACKAGE-default}
case "$enableval" in
yes) enable_static=yes ;;
no) enable_static=no ;;
*)
  enable_static=no
  # Look at the argument we got.  We use all the common list separators.
  IFS="${IFS= 	}"; ac_save_ifs="$IFS"; IFS="${IFS}:,"
  for pkg in $enableval; do
    if test "X$pkg" = "X$p"; then
      enable_static=yes
    fi
  done
  IFS="$ac_save_ifs"
  ;;
esac],
enable_static=AC_ENABLE_STATIC_DEFAULT)dnl
])

# AC_DISABLE_STATIC - set the default static flag to --disable-static
AC_DEFUN(AC_DISABLE_STATIC, [AC_BEFORE([$0],[AC_LIBTOOL_SETUP])dnl
AC_ENABLE_STATIC(no)])


# AC_ENABLE_FAST_INSTALL - implement the --enable-fast-install flag
# Usage: AC_ENABLE_FAST_INSTALL[(DEFAULT)]
#   Where DEFAULT is either `yes' or `no'.  If omitted, it defaults to
#   `yes'.
AC_DEFUN(AC_ENABLE_FAST_INSTALL, [dnl
define([AC_ENABLE_FAST_INSTALL_DEFAULT], ifelse($1, no, no, yes))dnl
AC_ARG_ENABLE(fast-install,
changequote(<<, >>)dnl
<<  --enable-fast-install[=PKGS]  optimize for fast installation [default=>>AC_ENABLE_FAST_INSTALL_DEFAULT],
changequote([, ])dnl
[p=${PACKAGE-default}
case "$enableval" in
yes) enable_fast_install=yes ;;
no) enable_fast_install=no ;;
*)
  enable_fast_install=no
  # Look at the argument we got.  We use all the common list separators.
  IFS="${IFS= 	}"; ac_save_ifs="$IFS"; IFS="${IFS}:,"
  for pkg in $enableval; do
    if test "X$pkg" = "X$p"; then
      enable_fast_install=yes
    fi
  done
  IFS="$ac_save_ifs"
  ;;
esac],
enable_fast_install=AC_ENABLE_FAST_INSTALL_DEFAULT)dnl
])

# AC_ENABLE_FAST_INSTALL - set the default to --disable-fast-install
AC_DEFUN(AC_DISABLE_FAST_INSTALL, [AC_BEFORE([$0],[AC_LIBTOOL_SETUP])dnl
AC_ENABLE_FAST_INSTALL(no)])

# AC_PROG_LD - find the path to the GNU or non-GNU linker
AC_DEFUN(AC_PROG_LD,
[AC_ARG_WITH(gnu-ld,
[  --with-gnu-ld           assume the C compiler uses GNU ld [default=no]],
test "$withval" = no || with_gnu_ld=yes, with_gnu_ld=no)
AC_REQUIRE([AC_PROG_CC])dnl
AC_REQUIRE([AC_CANONICAL_HOST])dnl
AC_REQUIRE([AC_CANONICAL_BUILD])dnl
ac_prog=ld
if test "$ac_cv_prog_gcc" = yes; then
  # Check if gcc -print-prog-name=ld gives a path.
  AC_MSG_CHECKING([for ld used by GCC])
  ac_prog=`($CC -print-prog-name=ld) 2>&5`
  case "$ac_prog" in
    # Accept absolute paths.
changequote(,)dnl
    [\\/]* | [A-Za-z]:[\\/]*)
      re_direlt='/[^/][^/]*/\.\./'
changequote([,])dnl
      # Canonicalize the path of ld
      ac_prog=`echo $ac_prog| sed 's%\\\\%/%g'`
      while echo $ac_prog | grep "$re_direlt" > /dev/null 2>&1; do
	ac_prog=`echo $ac_prog| sed "s%$re_direlt%/%"`
      done
      test -z "$LD" && LD="$ac_prog"
      ;;
  "")
    # If it fails, then pretend we aren't using GCC.
    ac_prog=ld
    ;;
  *)
    # If it is relative, then search for the first ld in PATH.
    with_gnu_ld=unknown
    ;;
  esac
elif test "$with_gnu_ld" = yes; then
  AC_MSG_CHECKING([for GNU ld])
else
  AC_MSG_CHECKING([for non-GNU ld])
fi
AC_CACHE_VAL(ac_cv_path_LD,
[if test -z "$LD"; then
  IFS="${IFS= 	}"; ac_save_ifs="$IFS"; IFS="${IFS}${PATH_SEPARATOR-:}"
  for ac_dir in $PATH; do
    test -z "$ac_dir" && ac_dir=.
    if test -f "$ac_dir/$ac_prog" || test -f "$ac_dir/$ac_prog$ac_exeext"; then
      ac_cv_path_LD="$ac_dir/$ac_prog"
      # Check to see if the program is GNU ld.  I'd rather use --version,
      # but apparently some GNU ld's only accept -v.
      # Break only if it was the GNU/non-GNU ld that we prefer.
      if "$ac_cv_path_LD" -v 2>&1 < /dev/null | egrep '(GNU|with BFD)' > /dev/null; then
	test "$with_gnu_ld" != no && break
      else
	test "$with_gnu_ld" != yes && break
      fi
    fi
  done
  IFS="$ac_save_ifs"
else
  ac_cv_path_LD="$LD" # Let the user override the test with a path.
fi])
LD="$ac_cv_path_LD"
if test -n "$LD"; then
  AC_MSG_RESULT($LD)
else
  AC_MSG_RESULT(no)
fi
test -z "$LD" && AC_MSG_ERROR([no acceptable ld found in \$PATH])
AC_PROG_LD_GNU
])

AC_DEFUN(AC_PROG_LD_GNU,
[AC_CACHE_CHECK([if the linker ($LD) is GNU ld], ac_cv_prog_gnu_ld,
[# I'd rather use --version here, but apparently some GNU ld's only accept -v.
if $LD -v 2>&1 </dev/null | egrep '(GNU|with BFD)' 1>&5; then
  ac_cv_prog_gnu_ld=yes
else
  ac_cv_prog_gnu_ld=no
fi])
])

# AC_PROG_NM - find the path to a BSD-compatible name lister
AC_DEFUN(AC_PROG_NM,
[AC_MSG_CHECKING([for BSD-compatible nm])
AC_CACHE_VAL(ac_cv_path_NM,
[if test -n "$NM"; then
  # Let the user override the test.
  ac_cv_path_NM="$NM"
else
  IFS="${IFS= 	}"; ac_save_ifs="$IFS"; IFS="${IFS}${PATH_SEPARATOR-:}"
  for ac_dir in $PATH /usr/ccs/bin /usr/ucb /bin; do
    test -z "$ac_dir" && ac_dir=.
    if test -f $ac_dir/nm || test -f $ac_dir/nm$ac_exeext ; then
      # Check to see if the nm accepts a BSD-compat flag.
      # Adding the `sed 1q' prevents false positives on HP-UX, which says:
      #   nm: unknown option "B" ignored
      if ($ac_dir/nm -B /dev/null 2>&1 | sed '1q'; exit 0) | egrep /dev/null >/dev/null; then
	ac_cv_path_NM="$ac_dir/nm -B"
	break
      elif ($ac_dir/nm -p /dev/null 2>&1 | sed '1q'; exit 0) | egrep /dev/null >/dev/null; then
	ac_cv_path_NM="$ac_dir/nm -p"
	break
      else
	ac_cv_path_NM=${ac_cv_path_NM="$ac_dir/nm"} # keep the first match, but
	continue # so that we can try to find one that supports BSD flags
      fi
    fi
  done
  IFS="$ac_save_ifs"
  test -z "$ac_cv_path_NM" && ac_cv_path_NM=nm
fi])
NM="$ac_cv_path_NM"
AC_MSG_RESULT([$NM])
])

# AC_CHECK_LIBM - check for math library
AC_DEFUN(AC_CHECK_LIBM,
[AC_REQUIRE([AC_CANONICAL_HOST])dnl
LIBM=
case "$lt_target" in
*-*-beos* | *-*-cygwin*)
  # These system don't have libm
  ;;
*-ncr-sysv4.3*)
  AC_CHECK_LIB(mw, _mwvalidcheckl, LIBM="-lmw")
  AC_CHECK_LIB(m, main, LIBM="$LIBM -lm")
  ;;
*)
  AC_CHECK_LIB(m, main, LIBM="-lm")
  ;;
esac
])

# AC_LIBLTDL_CONVENIENCE[(dir)] - sets LIBLTDL to the link flags for
# the libltdl convenience library and INCLTDL to the include flags for
# the libltdl header and adds --enable-ltdl-convenience to the
# configure arguments.  Note that LIBLTDL and INCLTDL are not
# AC_SUBSTed, nor is AC_CONFIG_SUBDIRS called.  If DIR is not
# provided, it is assumed to be `libltdl'.  LIBLTDL will be prefixed
# with '${top_builddir}/' and INCLTDL will be prefixed with
# '${top_srcdir}/' (note the single quotes!).  If your package is not
# flat and you're not using automake, define top_builddir and
# top_srcdir appropriately in the Makefiles.
AC_DEFUN(AC_LIBLTDL_CONVENIENCE, [AC_BEFORE([$0],[AC_LIBTOOL_SETUP])dnl
  case "$enable_ltdl_convenience" in
  no) AC_MSG_ERROR([this package needs a convenience libltdl]) ;;
  "") enable_ltdl_convenience=yes
      ac_configure_args="$ac_configure_args --enable-ltdl-convenience" ;;
  esac
  LIBLTDL='${top_builddir}/'ifelse($#,1,[$1],['libltdl'])/libltdlc.la
  INCLTDL='-I${top_srcdir}/'ifelse($#,1,[$1],['libltdl'])
])

# AC_LIBLTDL_INSTALLABLE[(dir)] - sets LIBLTDL to the link flags for
# the libltdl installable library and INCLTDL to the include flags for
# the libltdl header and adds --enable-ltdl-install to the configure
# arguments.  Note that LIBLTDL and INCLTDL are not AC_SUBSTed, nor is
# AC_CONFIG_SUBDIRS called.  If DIR is not provided and an installed
# libltdl is not found, it is assumed to be `libltdl'.  LIBLTDL will
# be prefixed with '${top_builddir}/' and INCLTDL will be prefixed
# with '${top_srcdir}/' (note the single quotes!).  If your package is
# not flat and you're not using automake, define top_builddir and
# top_srcdir appropriately in the Makefiles.
# In the future, this macro may have to be called after AC_PROG_LIBTOOL.
AC_DEFUN(AC_LIBLTDL_INSTALLABLE, [AC_BEFORE([$0],[AC_LIBTOOL_SETUP])dnl
  AC_CHECK_LIB(ltdl, main,
  [test x"$enable_ltdl_install" != xyes && enable_ltdl_install=no],
  [if test x"$enable_ltdl_install" = xno; then
     AC_MSG_WARN([libltdl not installed, but installation disabled])
   else
     enable_ltdl_install=yes
   fi
  ])
  if test x"$enable_ltdl_install" = x"yes"; then
    ac_configure_args="$ac_configure_args --enable-ltdl-install"
    LIBLTDL='${top_builddir}/'ifelse($#,1,[$1],['libltdl'])/libltdl.la
    INCLTDL='-I${top_srcdir}/'ifelse($#,1,[$1],['libltdl'])
  else
    ac_configure_args="$ac_configure_args --enable-ltdl-install=no"
    LIBLTDL="-lltdl"
    INCLTDL=
  fi
])

dnl old names
AC_DEFUN(AM_PROG_LIBTOOL, [indir([AC_PROG_LIBTOOL])])dnl
AC_DEFUN(AM_ENABLE_SHARED, [indir([AC_ENABLE_SHARED], $@)])dnl
AC_DEFUN(AM_ENABLE_STATIC, [indir([AC_ENABLE_STATIC], $@)])dnl
AC_DEFUN(AM_DISABLE_SHARED, [indir([AC_DISABLE_SHARED], $@)])dnl
AC_DEFUN(AM_DISABLE_STATIC, [indir([AC_DISABLE_STATIC], $@)])dnl
AC_DEFUN(AM_PROG_LD, [indir([AC_PROG_LD])])dnl
AC_DEFUN(AM_PROG_NM, [indir([AC_PROG_NM])])dnl

dnl This is just to silence aclocal about the macro not being used
ifelse([AC_DISABLE_FAST_INSTALL])dnl

# Do all the work for Automake.  This macro actually does too much --
# some checks are only needed if your package does certain things.
# But this isn't really a big deal.

# serial 1

dnl Usage:
dnl AM_INIT_AUTOMAKE(package,version, [no-define])

AC_DEFUN(AM_INIT_AUTOMAKE,
[AC_REQUIRE([AC_PROG_INSTALL])
PACKAGE=[$1]
AC_SUBST(PACKAGE)
VERSION=[$2]
AC_SUBST(VERSION)
dnl test to see if srcdir already configured
if test "`cd $srcdir && pwd`" != "`pwd`" && test -f $srcdir/config.status; then
  AC_MSG_ERROR([source directory already configured; run "make distclean" there first])
fi
ifelse([$3],,
AC_DEFINE_UNQUOTED(PACKAGE, "$PACKAGE", [Name of package])
AC_DEFINE_UNQUOTED(VERSION, "$VERSION", [Version number of package]))
AC_REQUIRE([AM_SANITY_CHECK])
AC_REQUIRE([AC_ARG_PROGRAM])
dnl FIXME This is truly gross.
missing_dir=`cd $ac_aux_dir && pwd`
AM_MISSING_PROG(ACLOCAL, aclocal, $missing_dir)
AM_MISSING_PROG(AUTOCONF, autoconf, $missing_dir)
AM_MISSING_PROG(AUTOMAKE, automake, $missing_dir)
AM_MISSING_PROG(AUTOHEADER, autoheader, $missing_dir)
AM_MISSING_PROG(MAKEINFO, makeinfo, $missing_dir)
AC_REQUIRE([AC_PROG_MAKE_SET])])

#
# Check to make sure that the build environment is sane.
#

AC_DEFUN(AM_SANITY_CHECK,
[AC_MSG_CHECKING([whether build environment is sane])
# Just in case
sleep 1
echo timestamp > conftestfile
# Do `set' in a subshell so we don't clobber the current shell's
# arguments.  Must try -L first in case configure is actually a
# symlink; some systems play weird games with the mod time of symlinks
# (eg FreeBSD returns the mod time of the symlink's containing
# directory).
if (
   set X `ls -Lt $srcdir/configure conftestfile 2> /dev/null`
   if test "[$]*" = "X"; then
      # -L didn't work.
      set X `ls -t $srcdir/configure conftestfile`
   fi
   if test "[$]*" != "X $srcdir/configure conftestfile" \
      && test "[$]*" != "X conftestfile $srcdir/configure"; then

      # If neither matched, then we have a broken ls.  This can happen
      # if, for instance, CONFIG_SHELL is bash and it inherits a
      # broken ls alias from the environment.  This has actually
      # happened.  Such a system could not be considered "sane".
      AC_MSG_ERROR([ls -t appears to fail.  Make sure there is not a broken
alias in your environment])
   fi

   test "[$]2" = conftestfile
   )
then
   # Ok.
   :
else
   AC_MSG_ERROR([newly created file is older than distributed files!
Check your system clock])
fi
rm -f conftest*
AC_MSG_RESULT(yes)])

dnl AM_MISSING_PROG(NAME, PROGRAM, DIRECTORY)
dnl The program must properly implement --version.
AC_DEFUN(AM_MISSING_PROG,
[AC_MSG_CHECKING(for working $2)
# Run test in a subshell; some versions of sh will print an error if
# an executable is not found, even if stderr is redirected.
# Redirect stdin to placate older versions of autoconf.  Sigh.
if ($2 --version) < /dev/null > /dev/null 2>&1; then
   $1=$2
   AC_MSG_RESULT(found)
else
   $1="$3/missing $2"
   AC_MSG_RESULT(missing)
fi
AC_SUBST($1)])



dnl
dnl Doxygen related macros
dnl



AC_DEFUN(LAC_DOXYGEN_PROJECT,dnl
[
    lac_doxygen_project=`echo "$1" | sed -e 's/_/ /g'`
    AC_SUBST(lac_doxygen_project)
])

AC_DEFUN(LAC_DOXYGEN_SOURCE_DIRS,dnl
[
    lac_doxygen_srcdirs=[$1]
    AC_SUBST(lac_doxygen_srcdirs)
])


AC_DEFUN(LAC_DOXYGEN_OUTPUT_TAGFILE,dnl
[
    lac_doxygen_output_tagfile=[$1]
    AC_SUBST(lac_doxygen_output_tagfile)
])

AC_DEFUN(LAC_DOXYGEN_TAGFILES,dnl
[
    lac_doxygen_tagfiles=""
    for x in "" $1; do
        if test "X$x" != "X" ; then
        lac_tag_base=`echo ${x} | sed -e 's|.*/||' -e 's|\.tag$||'`
        lac_tag="${lac_tag_base}.tag"
            lac_doxygen_tagfiles="$lac_doxygen_tagfiles $x"
            lac_doxygen_internal_tagfiles="$lac_doxygen_internal_tagfiles ${x}i"
        lac_doxygen_installdox="$lac_doxygen_installdox -l${lac_tag}@../../${lac_tag_base}/html"
    fi
    done
    AC_SUBST(lac_doxygen_tagfiles)
    AC_SUBST(lac_doxygen_internal_tagfiles)
    AC_SUBST(lac_doxygen_installdox)
])

AC_DEFUN(LAC_DOXYGEN_FILE_PATTERNS,dnl
[
    lac_doxygen_file_patterns=[$1]
])

AC_DEFUN(LAC_DOXYGEN_EXAMPLE_DIR,dnl
[
    lac_doxygen_examples=[$1]
])

AC_DEFUN(LAC_DOXYGEN_PREDEFINES,dnl
[
    lac_doxygen_predefines=[$1]
])

AC_DEFUN(LAC_DOXYGEN,dnl
[
    AC_ARG_ENABLE(doxygen,
    changequote(<<, >>)dnl  
<< --enable-doxygen[=PATH]     use Doxygen to generate documentation>>,
    changequote([, ])dnl
    [
        if test "$enableval" = "yes"; then
        AC_PATH_PROG(DOXYGEN,
            doxygen,
            [
            AC_MSG_ERROR(Doxygen installation not found)
            ])
        else
        DOXYGEN="$enableval"
        AC_SUBST(DOXYGEN)
        fi
    ],
    [
        DOXYGEN=""
        AC_SUBST(DOXYGEN)
    ])


    AC_ARG_ENABLE(internal-doc,
    [ --enable-internal-doc        Generate Doxygen documentation for
                   internal functions. Requires --enable-doxygen],
    [
    DOXYFILE="Doxyfile-internal"
    AC_SUBST(DOXYFILE) 
    ],
    [
    DOXYFILE="Doxyfile"
    AC_SUBST(DOXYFILE)
    ])


    if test -n "$DOXYGEN" ; then
    AC_PATH_PROG(DOT, dot)
    
    if test -z "$GLOBUS_SH_PERL" ; then
        AC_PATH_PROG(PERL, perl)
    else
        PERL="$GLOBUS_SH_PERL"
        AC_SUBST(PERL)
    fi
    if test "$DOT" != ""; then
        HAVE_DOT=YES
    else
        HAVE_DOT=NO
    fi

    AC_SUBST(HAVE_DOT)

    LAC_DOXYGEN_SOURCE_DIRS($1)
    LAC_DOXYGEN_FILE_PATTERNS($2)   

    LAC_DOXYGEN_PROJECT($GPT_NAME)
    LAC_DOXYGEN_OUTPUT_TAGFILE($GPT_NAME)

    lac_dep_check="$GLOBUS_LOCATION/sbin/globus-build-doxygen-dependencies"

    if test ! -x $lac_dep_check ; then

        # assume we are dealing with common
        
        lac_dep_check="$srcdir/scripts/globus-build-doxygen-dependencies"
        chmod 0755 $lac_dep_check

    fi

    AC_MSG_CHECKING([documentation dependencies])

    tagfiles="`$lac_dep_check -src $srcdir/pkgdata/pkg_data_src.gpt.in 2>/dev/null`"
    if test "$?" != "0"; then
        AC_MSG_RESULT([failed])
        AC_MSG_ERROR([Documentation dependencies could not be satisfied.])
    else
        AC_MSG_RESULT([ok])
    fi

    LAC_DOXYGEN_TAGFILES($tagfiles)

    AC_SUBST(lac_doxygen_file_patterns)
    AC_SUBST(lac_doxygen_examples)
    AC_SUBST(lac_doxygen_predefines)
    fi
]
)


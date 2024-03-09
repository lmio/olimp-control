#!/bin/bash

# Required packages: build-essential, debhelper, devscripts
#
# For more info on building deb packages, see:
#   https://www.debian.org/doc/manuals/maint-guide/
#   https://wiki.debian.org/Packaging

ver='1.1'
projdir="olimp-control-${ver}"
projtar="olimp-control_${ver}.orig.tar.gz"
builddir="build"

mkdir "${builddir}"
git archive --format=tar.gz --prefix="${projdir}/" --output="${builddir}/${projtar}" HEAD
cd "${builddir}"
tar -xzf "${projtar}"
cd "${projdir}/debian"
debuild -A -us -uc

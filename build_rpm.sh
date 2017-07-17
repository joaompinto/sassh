#!/bin/sh
set -xv
set -e
PACKAGE_NAME="sassh"
version=$(grep "%define version" ${PACKAGE_NAME}.spec | cut -d" " -f3)
rm -rf /tmp/${PACKAGE_NAME}-$version
cp -a . /tmp/${PACKAGE_NAME}-$version
cd /tmp && tar cvf ${PACKAGE_NAME}-$version.tar.gz ${PACKAGE_NAME}-$version
mv ${PACKAGE_NAME}-$version.tar.gz $HOME/rpmbuild/SOURCES
cd -
rpmbuild -ba ${PACKAGE_NAME}.spec

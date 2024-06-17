#!/bin/bash -xe

BUILDDIR="builddir"
MESON_OUTDIR="build"
DEB_OUTDIR="./"
ROOT_DIR=$(dirname "$(readlink -f "$0")")
ROOT_DIR="${ROOT_DIR}"/..

create_copyright(){
    if [ ! -d "${PKG_DOCDIR}" ]; then
        mkdir -p "${PKG_DOCDIR}"
        chmod --recursive 755 "${DOCDIR}"
    fi

    echo "Copyright Contributors to the Eclipse BlueChi project" >> "${PKG_DOCDIR}"/copyright
    chmod 644 "${PKG_DOCDIR}"/copyright
}

create_changelog(){
    if [ ! -d "${PKG_DOCDIR}" ]; then
        mkdir -p "${PKG_DOCDIR}"
        chmod --recursive 755 "${DOCDIR}"
    fi

    echo "A lot changed..." >> "${PKG_DOCDIR}"/changelog
    chmod 644 "${PKG_DOCDIR}"/changelog
    gzip -9n "${PKG_DOCDIR}"/changelog
}

create_debian_control(){
    DEPENDS="systemd:Depends"
    if [ "${PACKAGE_NAME}" == "bluechictl"]; then
        DEPENDS="${DEPENDS}"", bluechi-controller:Depends"
    fi
    echo """Source: bluechi
Section: x11
Version: ${VERSION}
Priority: optional
Maintainer: Michael Engel <mengel@redhat.com>
Build-Depends: debhelper (>=10), git (>=2.34.1), gcc (>=11.4.0), g++ (>=11.4.0), meson (>=1.2.1), systemd (>=249)
Homepage: https://github.com/eclipse-bluechi/bluechi
Package: ${PACKAGE_NAME}
Architecture: amd64
Depends: ${DEPENDS}
Description: BlueChi is a systemd service controller for multi-node environments with a
 predefined number of nodes and with a focus on highly regulated environment
 such as those requiring functional safety (for example in cars).
 .
 This package contains ${PACKAGE_NAME}.
""" > "${ROOT_DIR}"/"${BUILDDIR}"/"${MESON_OUTDIR}"/DEBIAN/control
}

create_debian_conffiles(){
    # create DEBIAN/conffiles
    CONFFILES_IN="${ROOT_DIR}"/"${BUILDDIR}"/"${MESON_OUTDIR}"/DEBIAN/conffiles.in
    touch "${CONFFILES_IN}"
    x=$(find "${BUILDDIR}"/"${MESON_OUTDIR}"/etc -type f -name '*.md')
    for file in ${x} ; do
        echo $file >> "${CONFFILES_IN}"
    done

    sed -e "s|${BUILDDIR}/${MESON_OUTDIR}||g" \
        < "${CONFFILES_IN}" \
        > "${ROOT_DIR}"/"${BUILDDIR}"/"${MESON_OUTDIR}"/DEBIAN/conffiles

    rm -f "${CONFFILES_IN}"
}

package_build_setup(){
    rm -rf "${BUILDDIR}"
    meson setup "${BUILDDIR}"
    meson configure "${BUILDDIR}" -Dwith_selinux=false
    meson configure "${BUILDDIR}" -Dprefix=/usr
    #meson configure "${BUILDDIR}" -Dlibexecdir=bin
}

package_build(){
    # Needed to fix:
    # lintian-explain-tags unstripped-binary-or-object
    # More info: https://www.debian.org/doc/debian-policy/ch-files.html#binaries
    strip --strip-unneeded --remove-section=.comment --remove-section=.note "${BUILDDIR}"/"${MESON_OUTDIR}"/usr/bin/*

    # gzip all man pages
    # lintian-explain-tags uncompressed-manual-page
    x=$(find "${BUILDDIR}"/"${MESON_OUTDIR}" -name *.[15])
    for file in ${x} ; do
        gzip -9n $file
    done
    # ...and remove selinux man pages
    x=$(find "${BUILDDIR}"/"${MESON_OUTDIR}" -name *.8)
    for file in ${x} ; do
        rm $file
    done

    create_debian_conffiles
    create_copyright
    create_changelog

    dpkg-deb --root-owner-group --build "${BUILDDIR}"/"${MESON_OUTDIR}"/ "${DEB_OUTDIR}"/"${PACKAGE_NAME}".deb
    dpkg-deb -c "${DEB_OUTDIR}"/"${PACKAGE_NAME}".deb
}

package_bluechi-controller(){
    meson install -C "${BUILDDIR}" --tags bluechi-controller --dest="${MESON_OUTDIR}"
    mkdir -p "${ROOT_DIR}"/"${BUILDDIR}"/"${MESON_OUTDIR}"/DEBIAN

    # create DEBIAN/control
    echo """Source: bluechi
Section: x11
Version: ${VERSION}
Priority: optional
Maintainer: Michael Engel <mengel@redhat.com>
Build-Depends: debhelper (>=10), git (>=2.34.1), gcc (>=11.4.0), g++ (>=11.4.0), meson (>=1.2.1), systemd (>=249)
Homepage: https://github.com/eclipse-bluechi/bluechi
Package: bluechi-controller
Architecture: amd64
Depends: systemd
Description: BlueChi is a systemd service controller for multi-node environments with a
 predefined number of nodes and with a focus on highly regulated environment
 such as those requiring functional safety (for example in cars).
 .
 This package contains the controller service.
""" > "${ROOT_DIR}"/"${BUILDDIR}"/"${MESON_OUTDIR}"/DEBIAN/control
}

package_bluechi-agent(){
    meson install -C "${BUILDDIR}" --tags bluechi-agent --dest="${MESON_OUTDIR}"
    mkdir -p "${ROOT_DIR}"/"${BUILDDIR}"/"${MESON_OUTDIR}"/DEBIAN

    # create DEBIAN/control
    echo """Source: bluechi
Section: x11
Version: ${VERSION}
Priority: optional
Maintainer: Michael Engel <mengel@redhat.com>
Build-Depends: debhelper (>=10), git (>=2.34.1), gcc (>=11.4.0), g++ (>=11.4.0), meson (>=1.2.1), systemd (>=249)
Homepage: https://github.com/eclipse-bluechi/bluechi
Package: bluechi-agent
Architecture: amd64
Depends: systemd
Description: BlueChi is a systemd service controller for multi-node environments with a
 predefined number of nodes and with a focus on highly regulated environment
 such as those requiring functional safety (for example in cars).
 .
 This package contains the agent service.
""" > "${ROOT_DIR}"/"${BUILDDIR}"/"${MESON_OUTDIR}"/DEBIAN/control
}


package_bluechictl(){
    meson install -C "${BUILDDIR}" --tags bluechictl --dest="${MESON_OUTDIR}"
    mkdir -p "${ROOT_DIR}"/"${BUILDDIR}"/"${MESON_OUTDIR}"/DEBIAN

    # create DEBIAN/control
    echo """Source: bluechi
Section: x11
Version: ${VERSION}
Priority: optional
Maintainer: Michael Engel <mengel@redhat.com>
Build-Depends: debhelper (>=10), git (>=2.34.1), gcc (>=11.4.0), g++ (>=11.4.0), meson (>=1.2.1), systemd (>=249)
Homepage: https://github.com/eclipse-bluechi/bluechi
Package: bluechictl
Architecture: amd64
Depends: systemd, bluechi-controller
Description: BlueChi is a systemd service controller for multi-node environments with a
 predefined number of nodes and with a focus on highly regulated environment
 such as those requiring functional safety (for example in cars).
 .
 This package contains bluechictl.
""" > "${ROOT_DIR}"/"${BUILDDIR}"/"${MESON_OUTDIR}"/DEBIAN/control
}

PACKAGE_NAME=$1
VERSION=$2

[ -z ${PACKAGE_NAME} ] && echo "Requires package name as first parameter." && exit 1
[ -z ${VERSION} ] && echo "Requires version as second parameter." && exit 1

DOCDIR="${ROOT_DIR}"/"${BUILDDIR}"/"${MESON_OUTDIR}"/usr/share/doc

if [ "${PACKAGE_NAME}" == "all" ]; then
    PACKAGE_NAME="bluechi-controller"
    PKG_DOCDIR="${DOCDIR}"/"${PACKAGE_NAME}"
    package_build_setup
    package_bluechi-controller
    package_build

    PACKAGE_NAME="bluechi-agent"
    PKG_DOCDIR="${DOCDIR}"/"${PACKAGE_NAME}"
    package_build_setup
    package_bluechi-agent
    package_build

    PACKAGE_NAME="bluechictl"
    PKG_DOCDIR="${DOCDIR}"/"${PACKAGE_NAME}"
    package_build_setup
    package_bluechictl
    package_build
else
    PKG_DOCDIR="${DOCDIR}"/"${PACKAGE_NAME}"
    package_build_setup
    package_"${1}"
    package_build
fi

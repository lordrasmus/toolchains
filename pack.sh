#!/bin/bash

tc=$1

echo "Toolchain : $1"

if [[ $tc == */ ]]; then
	echo "  ohne / am ende angeben"
	exit 1
fi

if [ ! -e $tc ] ; then
	echo "  nicht gefunden"
	exit 1
fi

arch=$(grep ADK_TARGET_CPU_ARCH= .config)
arch="${arch/ADK_TARGET_CPU_ARCH=}"
arch="${arch/\"}"
arch="${arch/\"}"

gcc="none"
if [[ $(grep ADK_TOOLCHAIN_GCC_7 .config) == "ADK_TOOLCHAIN_GCC_7=y" ]]; then   gcc="7"  ; fi
if [[ $(grep ADK_TOOLCHAIN_GCC_8 .config) == "ADK_TOOLCHAIN_GCC_8=y" ]]; then   gcc="8"  ; fi
if [[ $(grep ADK_TOOLCHAIN_GCC_9 .config) == "ADK_TOOLCHAIN_GCC_9=y" ]]; then   gcc="9"  ; fi
if [[ $(grep ADK_TOOLCHAIN_GCC_10 .config) == "ADK_TOOLCHAIN_GCC_10=y" ]]; then   gcc="10"  ; fi
if [[ $(grep ADK_TOOLCHAIN_GCC_11 .config) == "ADK_TOOLCHAIN_GCC_11=y" ]]; then   gcc="11"  ; fi
if [[ $(grep ADK_TOOLCHAIN_GCC_12 .config) == "ADK_TOOLCHAIN_GCC_12=y" ]]; then   gcc="12"  ; fi
if [[ $(grep ADK_TOOLCHAIN_GCC_13 .config) == "ADK_TOOLCHAIN_GCC_13=y" ]]; then   gcc="13"  ; fi

if [[ $gcc == "none" ]] ; then echo "No GCC detect"; exit 1 ; fi

echo ""
echo "GCC : $gcc"
echo "ARCH: $arch"
echo ""

cp .config $tc/config
cp /etc/os-release $tc


target=$(grep ADK_TARGET_SYSTEM= .config)
target="${target/ADK_TARGET_SYSTEM=}"
target="${target/\"}"
target="${target/\"}"

lib=$(grep ADK_TARGET_LIBC= .config)
lib="${lib/ADK_TARGET_LIBC=}"
lib="${lib/\"}"
lib="${lib/\"}"

tc2="toolchain-"$arch"-gcc-"$gcc

sysroot_path="target_"$target"_"$lib

if grep -q 'ADK_TARGET_CPU_TYPE' .config; then
	tmp=$(grep ADK_TARGET_CPU_TYPE= .config)
	tmp="${tmp/ADK_TARGET_CPU_TYPE=}"
	tmp="${tmp/\"}"
	tmp="${tmp/\"}"

	sysroot_path=$sysroot_path"_"$tmp
	tc2="toolchain-"$arch"_"$tmp"-gcc-"$gcc
fi

if [ ! -e $sysroot_path/usr/lib/crt1.o ] ; then
	echo "Sysroot unvollständig : suche $sysroot_path"
	exit 1
fi

mkdir -p $tc/sysroot
cp -r $sysroot_path/* $tc/sysroot


#echo "$tc2"
#exit 1


rm -rf $tc2
cp -r $tc $tc2

rm -f $tc2.tar.xz
tar -cvf $tc2.tar $tc2
xz -e -9 -v $tc2.tar


if [ ! -e toolchains ] ; then
	git clone git@github.com:lordrasmus/toolchains.git
fi

if [ ! -e toolchains ] ; then
	echo "toolchain git error"
	exit 1
fi
cp $tc2.tar.xz toolchains
( cd toolchains; git add $tc2.tar.xz; git commit -m "toolchain $tc2" )

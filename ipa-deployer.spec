Name: ipa-deployer
Version: %{_version}
Release: 1%{?dist}
Summary: Deployment image for ironic python agent

License: %{_platform_licence}
Source0: %{name}-%{version}.tar.gz
Vendor:  %{_platform_vendor}

BuildRequires: qemu-img-ev which sudo PyYAML e2fsprogs genisoimage wget kernel python2-ironic-python-agent python-ironic-lib python-devel xz python-pip gdisk dosfstools util-linux
%ifarch x86_64 amd64
BuildRequires: syslinux
%endif

%define dib_selinuxfile elements/rpm-distro/cleanup.d/99-selinux-fixfiles-restore
%define dib_epel elements/epel/pre-install.d/05-rpm-epel-release
%ifarch x86_64 amd64
%define centos_cloudimg https://cloud.centos.org/centos/7/images/CentOS-7-x86_64-GenericCloud-1801-01.qcow2
%define centos_mirror http://mirror.centos.org/centos/7
%else
%define centos_cloudimg https://cloud.centos.org/altarch/7/images/aarch64/CentOS-7-aarch64-GenericCloud-1708.qcow2.xz
%define centos_cloudimg_xz 1
%define centos_mirror http://mirror.centos.org/altarch/7
%endif
%define centos_efibootimg %{centos_mirror}/os/%{_arch}/images/efiboot.img
%define centos_efidir %{centos_mirror}/os/%{_arch}/EFI

%description
Deployment image for ironic python agent image

%prep
%autosetup

%build
sudo pip install diskimage-builder==2.26.1
sudo rm -rf %{python2_sitelib}/diskimage_builder/%{dib_selinuxfile} %{_datarootdir}§/diskimage-builder/%{dib_selinuxfile} %{python2_sitelib}/diskimage_builder/elements/epel/pre-install.d/05-rpm-epel-release
cp /etc/yum.conf work/local.repo
wget --progress=dot:giga %{centos_cloudimg} -O CentOS.qcow2%{?centos_cloudimg_xz:.xz}
%if 0%{?centos_cloudimg_xz:1}
unxz CentOS.qcow2.xz
%endif
url=%{centos_efidir}/
wget --progress=dot:giga %{centos_efibootimg} -O efiboot.img
cut_dirs=$(echo $url | sed -re 's|.*://[^/]+/(.+)|\1|' -e 's|/$||' | grep -o / | wc -l)
wget -N -r --no-host-directories --no-verbose --cut-dirs=${cut_dirs} --reject index.html* --no-parent $url
DIB_DEBUG_TRACE=1 \
  ELEMENTS_PATH="${PWD}/work/dib-ipa-element/" \
  DIB_LOCAL_IMAGE="file://${PWD}/CentOS.qcow2" \
  DIB_YUM_REPO_CONF="work/local.repo" \
  DIB_LOCAL_REPO="/usr/localrepo/" \
  break=after-error /usr/bin/disk-image-create  --install-type package localrepo centos7 virtmedia-netconf ironic-agent block-device-efi

if [[ $? == 0 ]]; then
  work/iso-image-create -o ./ironic-deploy.iso -i ./image.initramfs -k ./image.vmlinuz -e ./efiboot.img -E ./EFI
else
  echo "Failed to run disk-image-create"
fi

%install
mkdir -p %{buildroot}/opt/images/
rsync -av ironic-deploy.iso %{buildroot}/opt/images/

%files
%defattr(0755,root,root)
/opt/images/

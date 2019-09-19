Name: ipa-deployer
Version: %{_version}
Release: 1%{?dist}
Summary: Deployment image for ironic python agent

License: %{_platform_licence}
Source0: %{name}-%{version}.tar.gz
Vendor:  %{_platform_vendor}

BuildRequires: qemu-img-ev which sudo PyYAML e2fsprogs genisoimage wget kernel python2-ironic-python-agent python-ironic-lib python-devel
%ifarch x86_64 amd64
BuildRequires: diskimage-builder syslinux
%else
BuildRequires: xz python-pip gdisk dosfstools util-linux
%endif

%define dib_selinuxfile elements/rpm-distro/cleanup.d/99-selinux-fixfiles-restore
%define dib_epel elements/epel/pre-install.d/05-rpm-epel-release
%ifarch x86_64 amd64
%define centos_cloudimg https://cloud.centos.org/centos/7/images/CentOS-7-x86_64-GenericCloud-1801-01.qcow2
%else
%define centos_cloudimg https://cloud.centos.org/altarch/7/images/aarch64/CentOS-7-aarch64-GenericCloud-1708.qcow2.xz
%define centos_efibootimg http://mirror.centos.org/altarch/7/os/%{_arch}/images/efiboot.img
%endif

%description
Deployment image for ironic python agent image

%prep
%autosetup

%build
%ifnarch x86_64 amd64
sudo pip install diskimage-builder
%endif
sudo rm -rf %{python2_sitelib}/diskimage_builder/%{dib_selinuxfile} %{_datarootdir}§/diskimage-builder/%{dib_selinuxfile} %{python2_sitelib}/diskimage_builder/elements/epel/pre-install.d/05-rpm-epel-release
cp /etc/yum.conf work/local.repo
wget --progress=dot:giga %{centos_cloudimg} -O CentOS.qcow2%{?centos_efibootimg:.xz}
%ifnarch x86_64 amd64
unxz CentOS.qcow2.xz
wget --progress=dot:giga %{centos_efibootimg} -O efiboot.img
%endif
DIB_DEBUG_TRACE=1 \
  ELEMENTS_PATH="${PWD}/work/dib-ipa-element/" \
  DIB_LOCAL_IMAGE="file://${PWD}/CentOS.qcow2" \
  DIB_YUM_REPO_CONF="work/local.repo" \
  DIB_LOCAL_REPO="/usr/localrepo/" \
  break=after-error /usr/bin/disk-image-create  --install-type package localrepo centos7 virtmedia-netconf ironic-agent %{?centos_efibootimg:block-device-efi}

if [[ $? == 0 ]]; then
  work/iso-image-create -o ./ironic-deploy.iso -i ./image.initramfs -k ./image.vmlinuz %{?centos_efibootimg:-e ./efiboot.img}
else
  echo "Failed to run disk-image-create"
fi

%install
mkdir -p %{buildroot}/opt/images/
rsync -av ironic-deploy.iso %{buildroot}/opt/images/

%files
%defattr(0755,root,root)
/opt/images/

%define name sassh
%define version 0.4.4
%define release 0

Summary: SysAdmin SSH connection manager/client
Name: %{name}
Version: %{version}
Release: %{release}
Source0: %{name}-%{version}.tar.gz
License: UNKNOWN
Group: Development/Libraries
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-buildroot
Prefix: %{_prefix}
BuildArch: noarch
requires: python-paramiko, pygpgme, python-lxml, python2-pyxdg

%description
SysAdmin SSH connection manager/client

%prep
%setup -n %{name}-%{version}

%build
python setup.py build

%install
python setup.py install -O1 --root=$RPM_BUILD_ROOT --record=INSTALLED_FILES

%clean
rm -rf $RPM_BUILD_ROOT

%files -f INSTALLED_FILES
%defattr(-,root,root)

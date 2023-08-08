from setuptools import setup, find_packages

with open("requirements.txt") as f:
	install_requires = f.read().strip().split("\n")

# get version from __version__ variable in smm/__init__.py
from smm import __version__ as version

setup(
	name="smm",
	version=version,
	description="Social Media Marketing and Management system",
	author="mimiza",
	author_email="dev@mimiza.com",
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires
)

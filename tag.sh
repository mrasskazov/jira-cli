#!/bin/bash 
echo current version:$(python -c "import jiracli;print jiracli.__version__")
read -p "new version:" new_version
sed -i -e "s/__version__.*/__version__=\"${new_version}\"/g" jiracli/__init__.py 
git add jiracli/__init__.py
git commit -m "updating version to ${new_version}"
git tag -s -m "tagging version ${new_version}" $(python setup.py --version)
python setup.py build sdist bdist_egg upload



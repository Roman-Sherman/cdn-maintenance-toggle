# CDN Maintenance Toggle script

## Setup & Usage

Recommend installation is via a pipenv-managed virtualenv (with consistent
package versions tracked in the lock file), and pyenv to install the supported
Python release if your system doesn't have Python 3.11.

```bash
pyenv install 3.11
pipenv install
pipenv shell
export AWS_PROFILE=prdct-dev
./cdn_maintenance_toggle.py --template example.html -v --disable-sites "*.platform.linuxfoundation.org" "*.lfx.dev"
./cdn_maintenance_toggle.py -v --enable-sites "*.platform.linuxfoundation.org" "*.lfx.dev"
./cdn_maintenance_toggle.py --cleanup
```

Alternativelly, you can install the required Python packages system-wide or to
the current user. This tool has been developed against Python 3.11 and may not
work on other versions.

```bash
pip3.11 install --user boto3
# Optional: to set AWS_PROFILE or other parameters via .env:
# pip3.11 install --user python-dotenv
export AWS_PROFILE=prdct-dev
./cdn_maintenance_toggle.py --template example.html -v --disable-sites "*.platform.linuxfoundation.org" "*.lfx.dev"
./cdn_maintenance_toggle.py -v --enable-sites "*.platform.linuxfoundation.org" "*.lfx.dev"
./cdn_maintenance_toggle.py --cleanup
```

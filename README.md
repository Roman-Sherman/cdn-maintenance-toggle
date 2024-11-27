# CDN maintenance toggle script

This script disables/enables CDN services operating on AWS Cloudfront by
setting them into maintenance mode, implemented as a Cloudfront edge function
returning an HTML maintenance page.

Features include:

- Specify matching domain wildcards to limit affected Cloudfront services in
  the current AWS account/region.
- Provide IP addresses that are allowed to bypass the outage page for a
  disabled site.
- Specify a custom HTML template for the outage page.

For more details, run the script with the `--help` option.

## Setup & usage for Linux Foundation / LFX sites

Recommend installation is via a `uv` virtualenv, and `pyenv` to install the
supported Python release.

The script relies on the environment to provide AWS authentication and
determine which account to connect to. Export the `AWS_PROFILE` environment
variable, or run the script with `aws-vault`, depending on your setup.

```bash
pyenv install 3.12 # or: brew install python@3.12; brew pyenv-sync
make sync # requires `uv` to be installed
source .venv/bin/activate
./cdn_maintenance_toggle.py --template lfx-maintenance.html -v --disable-sites "*.platform.linuxfoundation.org" "*.lfx.dev"
./cdn_maintenance_toggle.py -v --enable-sites "*.platform.linuxfoundation.org" "*.lfx.dev"
./cdn_maintenance_toggle.py --cleanup
deactivate
```

Alternativelly, you can install the required Python packages system-wide or to
the current user. This tool has been developed against Python 3.12 and may not
work on other versions.

```bash
pip install --user boto3 trieregex
# Optional: to set AWS_PROFILE or other parameters via .env:
# pip install --user python-dotenv
./cdn_maintenance_toggle.py --template lfx-maintenance.html -v --disable-sites "*.platform.linuxfoundation.org" "*.lfx.dev"
./cdn_maintenance_toggle.py -v --enable-sites "*.platform.linuxfoundation.org" "*.lfx.dev"
./cdn_maintenance_toggle.py --cleanup
```

## Customization

The HTML template `lfx-maintenance.html` is provided as an example of an outage
page used by the Linux Foundation for LFX Platform maintanance. Remove any
Linux Foundation / LFX branding before using this with any other sites.

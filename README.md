# CDN Maintenance Toggle script

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

## Setup & Usage for Linux Foundation / LFX sites

Recommend installation is via a pipenv-managed virtualenv (with consistent
package versions tracked in the lock file), and pyenv to install the supported
Python release if your system doesn't have Python 3.11.

Be sure to set `AWS_PROFILE` with MFA and/or SSO authentication helpers before
running the script.

```bash
pyenv install 3.11
pipenv install
pipenv shell
./cdn_maintenance_toggle.py --template lfx-maintenance.html -v --disable-sites "*.platform.linuxfoundation.org" "*.lfx.dev"
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
./cdn_maintenance_toggle.py --template lfx-maintenance.html -v --disable-sites "*.platform.linuxfoundation.org" "*.lfx.dev"
./cdn_maintenance_toggle.py -v --enable-sites "*.platform.linuxfoundation.org" "*.lfx.dev"
./cdn_maintenance_toggle.py --cleanup
```

## Customization

The HTML template `lfx-maintenance.html` is provided as an example of an outage
page used by the Linux Foundation for LFX Platform maintanance. Remove any
Linux Foundation / LFX branding before using this with any other sites.

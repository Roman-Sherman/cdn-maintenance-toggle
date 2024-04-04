#!/usr/bin/env python3.11
#
# Copyright The Linux Foundation and each contributor to LFX.
# SPDX-License-Identifier: MIT

"""
This script disables/enables CDN services operating on AWS Cloudfront by
setting them into maintenance mode, implemented as a Cloudfront edge function
returning an HTML maintenance page.
"""

import argparse
from base64 import b64encode
from hashlib import sha256
from fnmatch import fnmatch
import logging
import ipaddress
import os

import boto3
from botocore.exceptions import ClientError

from trieregex import TrieRegEx as TRE

# Optional support for .env file.
try:
    from dotenv import load_dotenv
except ImportError:
    pass
else:
    load_dotenv()

CLIENT = boto3.client('cloudfront')

FUNCTION_TEMPLATE = """function handler(event) {
  var headers;
  var response;
  if (event.viewer.ip.match(/^%s$/)) {
    if (event.context.eventType === 'viewer-request') {
      return event.request;
    }
    return event.response;
  }
  if (event.request.uri.match(/\\/[^/]+\\.[^/]+$/)) {
    if (event.context.eventType === 'viewer-request') {
      return event.request;
    }
    return event.response;
  }
  if (event.context.eventType === 'viewer-request') {
    headers = {
      'content-type': { value: 'text/html' },
      'cache-control': { value: 'no-cache, must-revalidate' },
      'x-client-ip': { value: event.viewer.ip },
      expires: { value: 'Sun, 19 Nov 1978 05:00:00 GMT' },
    };
  } else {
    headers = event.response.headers;
    delete headers['content-encoding'];
    delete headers['content-length'];
    headers['content-type'] = { value: 'text/html' };
    headers['cache-control'] = { value: 'no-cache, must-revalidate' };
    headers['x-client-ip'] = { value: event.viewer.ip };
    headers.expires = { value: 'Sun, 19 Nov 1978 05:00:00 GMT' };
  }
  response = {
    statusCode: 503,
    statusDescription: 'Service Unavailable',
    headers,
    body: {
      encoding: 'base64',
      data: '%s',
    },
  };
  return response;
}"""

def main():
    """main is the entry point for script invocations."""

    # Parse arguments from command line.
    parser = argparse.ArgumentParser(description='Set or clear maintenance notices on CloudFlare CDNs for the current AWS_PROFILE.')
    parser.add_argument('--dry-run', action='store_true', help='show actions to be taken without saving them')
    enable_disable = parser.add_mutually_exclusive_group(required=True)
    enable_disable.add_argument('--enable-sites', nargs='+', metavar='PATTERN', help='enable matching domains (clear maintenance page)')
    enable_disable.add_argument('--disable-sites', nargs='+', metavar='PATTERN', help='disable matching domains (set maintenance page)')
    enable_disable.add_argument('--cleanup', action='store_true', help='delete unused maintenance page functions')
    parser.add_argument('--template', type=argparse.FileType('r'), metavar='FILE', help='template file for HTML response')
    ip_source = parser.add_mutually_exclusive_group()
    ip_source.add_argument('--allow-ip', nargs='*', metavar='IP', help='IPs to bypass maintenance page')
    ip_source.add_argument('--allow-ip-file', type=argparse.FileType('r'), metavar='FILE', help='read bypass IPs from file, one per line')
    parser.add_argument('-v', '--verbose', action='store_true', help='log actions taken')

    args = parser.parse_args()

    if os.getenv('DEBUG'):
        # Enable debug logging via undocumented environmental variable.
        logging.basicConfig(level=10)
    elif args.verbose:
        # Verbose mode will enable Info logging.
        logging.basicConfig(level=20)

    # Conditional for the 3 execution modes.
    if args.cleanup:
        cleanup(dry_run=args.dry_run)
    elif args.enable_sites:
        enable_sites(args.enable_sites, dry_run=args.dry_run)
    else:
        # Read IPs from parameters or from passed file. Validation happens
        # later.
        allowed_ips = []
        if args.allow_ip is not None:
            allowed_ips = args.allow_ip
        elif args.allow_ip_file is not None:
            allowed_ips = args.allow_ip_file.readlines()

        # Read custom HTML from passed file if provided. Fallback HTML is
        # defined later.
        html = None
        if args.template is not None:
            html = args.template.read()

        disable_sites(args.disable_sites, html=html, allowed_ips=allowed_ips, dry_run=args.dry_run)

def enable_sites(patterns, dry_run=False):
    """Enable sites matching patterns (clear maintenance page)."""

    targets = get_matching_distributions(patterns)

    if dry_run is True:
        logging.warning("running in dry-run mode: any logged changes are as-if")

    for distribution in targets:
        remove_maintenance_function(distribution, dry_run=dry_run)

def disable_sites(patterns, html=None, allowed_ips=tuple(), dry_run=False):
    """Disable sites matching patterns (set maintenance page)."""

    if html is None:
        # Fallback/default maintenance page HTML.
        html = '<!DOCTYPE html><html><body><p>This site is down for scheduled maintenance.</p></body></html>'

    # Find Cloudfront distributions matching the supplied domain patterns.
    targets = get_matching_distributions(patterns)

    if dry_run is True:
        logging.warning("running in dry-run mode: any logged changes are as-if")

    if len(targets) == 0:
        # Bypass function creation if there are no matching targets.
        return

    html_bytes = html.encode('utf8')

    # Validate passed IPs and build a trie regex pattern out of them.
    tre = TRE('127.0.0.1')
    for ip_text in allowed_ips:
        try:
            # Read IPv4 & IPv6 addresses.
            ip_addr = ipaddress.ip_address(ip_text.strip())
            if not ip_addr.is_global:
                logging.warning("ignoring non-global IP address: %s", ip_addr)
            else:
                tre.add(str(ip_addr))
        except ValueError:
            try:
                # Read IPv4 CIDR ranges (not IPv6 ranges ... too many addresses!).
                ip_net = ipaddress.IPv4Network(ip_text.strip(), strict=False)
                if ip_net.prefixlen < 28:
                    logging.warning("ignoring CIDR network larger than /28: %s", ip_net)
                elif not ip_net.is_global:
                    logging.warning("ignoring non-global IP network: %s", ip_net)
                else:
                    tre.add(*map(str, ip_net.hosts()))
            except ValueError:
                logging.warning("ignoring invalid/unsupported IP: %s", ip_text.strip())

    ip_pattern = tre.regex()

    # Interpolate allowed IPs and base64-encoded HTML into function template.
    function = FUNCTION_TEMPLATE % (ip_pattern, b64encode(html_bytes).decode('utf8'))

    # Create the function and get the hashed function name.
    function_name = create_function(function, dry_run)

    for distribution in targets:
        set_maintenance_function(distribution, function_name, dry_run=dry_run)

def cleanup(dry_run=False):
    """Delete unused maintenance pages."""

    if dry_run is True:
        logging.warning("running in dry-run mode: any logged changes are as-if")

    resp = CLIENT.list_functions()

    # Loop through a set of unique names, rather than all items, to deduplicate
    # DEV/LIVE stage.
    for function_name in {item['Name'] for item in resp['FunctionList']['Items'] if item['Name'][:12] == "maintenance-"}:
        logging.info("deleting function %s", function_name)

        if dry_run is True:
            continue

        etag = CLIENT.describe_function(Name=function_name)['ETag']

        try:
            CLIENT.delete_function(Name=function_name, IfMatch=etag)
        except ClientError as error:
            if error.response['Error']['Code'] == 'FunctionInUse':
                logging.warning("skipping deletion of active function: %s", function_name)
            else:
                raise error

def create_function(function, dry_run=False):
    """Idempotently create-if-not-exist the provided CloudFront function and return the function name."""

    if len(function) > 20000:
        raise ValueError("function is too big, try reducing allowed IPs")

    # Hash the function to calculate a unique function name.
    function_hash = sha256(function.encode('utf8')).hexdigest()
    function_name = f"maintenance-{function_hash[:12]}"

    resp = CLIENT.list_functions()

    found_name = False
    for item in resp['FunctionList']['Items']:
        if item['Name'] == function_name and item['FunctionMetadata']['Stage'] == "LIVE":
            logging.debug("found existing published function %s", function_name)
            return function_name
        if item['Name'] == function_name:
            # The function was found but not published.
            found_name = True

    if found_name:
        # This shouldn't happen, but if it does, attempt to publish the
        # function.
        logging.info("publishing function %s", function_name)
        if not dry_run:
            etag = CLIENT.describe_function(Name=function_name)['ETag']
            CLIENT.publish_function(Name=function_name, IfMatch=etag)
        return function_name

    # The function was not found, so it needs to be created and published.
    logging.info("creating function %s", function_name)
    if not dry_run:
        config = {
            'Comment': '503 maintenance page created by cdn_maintenance_toggle',
            'Runtime': 'cloudfront-js-1.0',
        }
        response = CLIENT.create_function(Name=function_name, FunctionConfig=config, FunctionCode=function.encode('utf8'))

    logging.info("publishing function %s", function_name)
    if not dry_run:
        CLIENT.publish_function(Name=function_name, IfMatch=response['ETag'])

    return function_name

def remove_maintenance_function(distribution, dry_run=False):
    """Idempotently remove any maintenance functions from a CloudFront distribution."""

    resp = CLIENT.get_distribution_config(Id=distribution['Id'])
    cache_config = resp['DistributionConfig']['DefaultCacheBehavior']

    needs_update = False

    if 'Items' not in cache_config['FunctionAssociations']:
        cache_config['FunctionAssociations']['Items'] = []
    for i, item in enumerate(cache_config['FunctionAssociations']['Items']):
        if item['EventType'] in ('viewer-request', 'viewer-response') and "maintenance-" in item['FunctionARN']:
            needs_update = True

            # Delete the maintenance function.
            logging.info("removing function %s from %s", item['FunctionARN'], ", ".join(distribution['Aliases']['Items']))

            cache_config['FunctionAssociations']['Quantity'] -= 1
            del cache_config['FunctionAssociations']['Items'][i]

    if not needs_update:
        # No maintenance functions detected.
        return

    if dry_run:
        return

    # Rename ETag to IfMatch to convert the response to a request.
    resp['IfMatch'] = resp['ETag']
    del resp['ETag']

    # Delete ResponseMetadata.
    del resp['ResponseMetadata']

    # Update the distribution to remove the function(s).
    CLIENT.update_distribution(Id=distribution['Id'], **resp)

def set_maintenance_function(distribution, function_name, dry_run=False):
    """Idempotently configure a request type function on a CloudFront distribution.

    The passed function_name must be a published CloudFront function or this function will raise an exception.
    """

    dist_response = CLIENT.get_distribution_config(Id=distribution['Id'])
    cache_config = dist_response['DistributionConfig']['DefaultCacheBehavior']

    if 'Items' in cache_config['LambdaFunctionAssociations']:
        if len([i for i in cache_config['LambdaFunctionAssociations']['Items'] if i['EventType'] in ('viewer-request', 'viewer-response')]) != 0:
            logging.error("cannot disable site with existing request or response Lambda functions: %s", ", ".join(distribution['Aliases']['Items']))
            return

    event_type = ''

    if 'Items' not in cache_config['FunctionAssociations']:
        cache_config['FunctionAssociations']['Items'] = []
    for i, item in enumerate(cache_config['FunctionAssociations']['Items']):
        if item['EventType'] in ('viewer-request', 'viewer-response')  and function_name in item['FunctionARN']:
            # This maintenance function is already set on this distribution.
            logging.debug("found %s function %s on %s", item['EventType'], function_name, ", ".join(distribution['Aliases']['Items']))
            return
        if item['EventType'] in ('viewer-request', 'viewer-response') and "maintenance-" in item['FunctionARN']:
            # Delete any previous maintenance functions with a different hash/name.
            logging.info("removing %s function %s from %s", item['EventType'], item['FunctionARN'], ", ".join(distribution['Aliases']['Items']))

            cache_config['FunctionAssociations']['Quantity'] -= 1
            del cache_config['FunctionAssociations']['Items'][i]

    if len([i for i in cache_config['FunctionAssociations']['Items'] if i['EventType'] == 'viewer-request']) == 0:
        # No other viewer-request functions; add as a request function.
        event_type = 'viewer-request'
    elif len([i for i in cache_config['FunctionAssociations']['Items'] if i['EventType'] == 'viewer-response']) == 0:
        # No other viewer-response functions; add as a response function.
        event_type = 'viewer-response'
    else:
        # Both viewer-request and viewer-response have non-maintenance-related functions.
        logging.error("cannot disable site with existing request and response functions: %s", ", ".join(distribution['Aliases']['Items']))
        return

    logging.info("adding %s function %s to %s", event_type, function_name, ", ".join(distribution['Aliases']['Items']))

    if dry_run:
        return

    # Stage the additional function.
    func_response = CLIENT.describe_function(Name=function_name, Stage='LIVE')
    function_metadata = func_response['FunctionSummary']['FunctionMetadata']
    cache_config['FunctionAssociations']['Items'].append({
        'FunctionARN': function_metadata['FunctionARN'],
        'EventType': event_type,
    })
    cache_config['FunctionAssociations']['Quantity'] += 1

    # Rename ETag to IfMatch to convert the response to a request.
    dist_response['IfMatch'] = dist_response['ETag']
    del dist_response['ETag']

    # Delete ResponseMetadata.
    del dist_response['ResponseMetadata']

    # Update the distribution to add our function.
    CLIENT.update_distribution(Id=distribution['Id'], **dist_response)

def get_matching_distributions(patterns):
    """Find Cloudfront distributions matching the supplied domain patterns."""

    distributions = []

    args = {}
    while True:
        # Fetch next batch of CloudFront distributions in the current AWS
        # account (global region).
        resp = CLIENT.list_distributions(**args)
        if 'Items' not in resp['DistributionList']:
            break
        for distribution in resp['DistributionList']['Items']:
            if 'Items' not in distribution['Aliases']:
                logging.warning("ignoring distribution %s with no domain aliases", distribution['Id'])
                continue
            for domain in distribution['Aliases']['Items']:
                if fnmatch_any(domain.lower(), patterns):
                    distributions.append(distribution)
                    # No need to check other domains in this distribution.
                    break

        if 'Marker' not in resp:
            # Final page of results.
            break

        args['NextMarker'] = resp['Marker']

    return distributions

def fnmatch_any(string, patterns):
    """Run fnmatch on multiple patterns and return True if any match, otherwise False."""

    for pattern in patterns:
        if fnmatch(string, pattern):
            return True
    return False

if __name__ == '__main__':
    main()

#!/usr/bin/env bash

# Copyright The Linux Foundation and each contributor to LFX.
# SPDX-License-Identifier: MIT

# A simple script that scans the go files checking for the license header.
# Exits with a 0 if all source files have license headers
# Exits with a 1 if one or more source files are missing a license header

# Exclude code coming from a third-party. Typically these won't be checked into
# source control, but occassionally "vendored" code is committed.
exclude_pattern='^(.*/)?(node_modules|vendor)/'

# Include build definitions.
filetypes=(Makefile Dockerfile .gitignore .dockerignore)
# Include Golang files.
filetypes+=("*.go" go.mod)
# Include Python files.
filetypes+=("*.py")
# Include HTML, CSS, JS, TS, SCSS.
filetypes+=("*.html" "*.htm" "*.css" "*.ts" "*.js" "*.scss")
# Include shell scripts.
filetypes+=("*.sh" "*.bash" "*.ksh" "*.csh" "*.tcsh" "*.fsh")
# Include text.
filetypes+=("*.txt")
# Include YAML and TOML files.
filetypes+=("*.yaml" "*.yml" "*.toml")
# Include SQL scripts and definitions.
filetypes+=("*.sql")

files=()
while IFS='' read -r line; do files+=("$line"); done < <(git ls-files -c "${filetypes[@]}" | grep -E -v "${exclude_pattern}")

# This is the copyright line to look for - adjust as necessary
copyright_line="Copyright The Linux Foundation"

# Flag to indicate if we were successful or not
missing_license_header=0

# For each file...
echo "Checking ${#files[@]} source code files for the license header..."
for file in "${files[@]}"; do
	# echo "Processing file ${file}..."

	# Header is typically one of the first few lines in the file...
	head -4 "${file}" | grep -q "${copyright_line}"
	# Find it? exit code value of 0 indicates the grep found a match
	exit_code=$?
	if [[ ${exit_code} -ne 0 ]]; then
		echo "${file} is missing the license header"
		# update our flag - we'll fail the test
		missing_license_header=1
	fi
done

# Summary
if [[ ${missing_license_header} -eq 1 ]]; then
	echo "One or more source files is missing the license header."
else
	echo "License check passed."
fi

# Exit with status code 0 = success, 1 = failed
exit ${missing_license_header}

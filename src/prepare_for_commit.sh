#!/bin/bash

printf "Preparing for commit...\n"

printf "Removing __pycache__ directories...\n"
find . -type d -name "__pycache__" -exec rm -rf {} \;

printf "Removing .vscode directory...\n"
rm -rf .vscode

printf "Removing config directory...\n"
rm -rf config

printf "Removing logs directory...\n"
sudo rm -rf logs

printf "Removing temp dir...\n"
rm -rf temp

printf "Ready for commit!\n"

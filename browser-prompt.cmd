@echo off
chcp 65001 >nul
node "%~dp0browser-prompt.js" %*

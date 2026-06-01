@echo off
chcp 65001 >nul
node "%~dp0browser-flow.js" %*

@echo off
REM Duplo-clique para compactar um disco/pasta inteira em um .zip pronto
REM para envio pela tela Configuracoes > Publicacoes do SAA29.
setlocal

where py >nul 2>nul
if %ERRORLEVEL%==0 (
    py "%~dp0zipar_disco.py"
) else (
    python "%~dp0zipar_disco.py"
)

echo.
pause

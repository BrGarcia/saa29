"""Script de correção dos routers: corrige ordem de parâmetros e NotImplementedError."""
import glob
import pathlib

NOT_IMPL = 'raise NotImplementedError'
HTTP_STUB = 'raise HTTPException(status_code=501, detail="Endpoint nao implementado - Dia 4")'

for f in glob.glob('app/**/router.py', recursive=True):
    txt = pathlib.Path(f).read_text(encoding='utf-8')
    # 1. Substituir NotImplementedError por HTTPException 501
    txt = txt.replace(NOT_IMPL, HTTP_STUB)
    # 2. Garantir que HTTPException esteja importado
    if 'HTTPException' in txt and 'HTTPException' not in txt[:txt.find('router = APIRouter')]:
        if 'from fastapi import APIRouter, Depends, HTTPException,' in txt:
            pass  # já importado
        elif 'from fastapi import APIRouter, Depends, HTTPException' in txt:
            pass  # já importado
        elif 'from fastapi import APIRouter, Depends,' in txt:
            txt = txt.replace('from fastapi import APIRouter, Depends,', 'from fastapi import APIRouter, Depends, HTTPException,', 1)
        elif 'from fastapi import APIRouter, Depends' in txt:
            txt = txt.replace('from fastapi import APIRouter, Depends', 'from fastapi import APIRouter, Depends, HTTPException', 1)
        elif 'from fastapi import APIRouter' in txt:
            txt = txt.replace('from fastapi import APIRouter', 'from fastapi import APIRouter, HTTPException', 1)
    pathlib.Path(f).write_text(txt, encoding='utf-8')
    print(f'OK: {f}')

print('Concluido.')

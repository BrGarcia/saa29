[TÍTULO]
Bug | Configurações | Upload XLSX do inventário falha e gera erro CSRF em nova tentativa

[CONTEXTO]
Módulo: Configurações  
Funcionalidade: “Carregamento Inventário (XLSX)”  
Endpoint: /equipamentos/inventario/upload-xlsx  
Arquivo utilizado: 5919.xlsx

[COMPORTAMENTO ATUAL]
Primeira tentativa:
Relatório — Aeronave 5919
Linhas lidas: 33
PNs encontrados: 12
PNs ignorados: 21
Itens atualizados: 33
Detalhes:
❓ ADF (622-7382-101) []: Não localizado no XLSX → XXXXXXX-ADF
❓ DME (622-7309-101) []: Não localizado no XLSX → XXXXXXX-DME
❓ TDR (622-9352-004) []: Não localizado no XLSX → XXXXXXX-TDR
❓ STORMSCOPE (78-8060-6086-5) []: Não localizado no XLSX → XXXXXXX-STORMSCOPE
❓ EGIR (34200802-80RB) []: Não localizado no XLSX → XXXXXXX-EGIR
❓ VOR (622-7194-201) []: Não localizado no XLSX → XXXXXXX-VOR
❓ MDP1 (MA902B-02) [EL1]: Não localizado no XLSX → XXXXXXX-MDP1
❓ MDP2 (MA902B-02) [EL2]: Não localizado no XLSX → XXXXXXX-MDP2
❓ ARTU (251-118-012-012) []: Não localizado no XLSX → XXXXXXX-ARTU
❓ AFDC (449100-02-01) []: Não localizado no XLSX → XXXXXXX-AFDC
✅ VUHF1 (6110.3001.12) → SN: 100049
✅ VUHF2 (6106.7006.12) → SN: 100074
✅ AMPMIC-1P (263-000) → SN: 442
❓ PDU (4455-1000-01) []: Não localizado no XLSX → XXXXXXX-PDU
❓ UFCP (4456-1000-02) []: Não localizado no XLSX → XXXXXXX-UFCP
❓ CHVC (VEC00054) []: Não localizado no XLSX → XXXXXXX-CHVC
✅ CMFD1 (MB387B-01) → SN: 2375
✅ CMFD2 (MB387B-01) → SN: 2335
✅ ASP-1P (343-001) → SN: 310
❓ GPS (066-04031-1622) []: Não localizado no XLSX → XXXXXXX-GPS
❓ PA CONTROL (449300-02-01) []: Não localizado no XLSX → XXXXXXX-PA CONTROL
❓ PIC/NAV (314-04895-403) []: Não localizado no XLSX → XXXXXXX-PIC/NAV
✅ STICKGRIP-1P (733-0402) → SN: 0343
❓ DVR (MB211E-03) []: Não localizado no XLSX → XXXXXXX-DVR
✅ AMPMIC-2P (263-000) → SN: 416
❓ PSU (4458-1000-00) []: Não localizado no XLSX → XXXXXXX-PSU
✅ CMFD3 (MB387B-01) → SN: 2296
∅ CMFD4 (MB387B-01): Removido (vazio no XLSX)
✅ ASP-2P (343-001) → SN: 286
✅ STICKGRIP-2P (733-0402) → SN: 0205U
❓ VADR (174521-10-01) []: Não localizado no XLSX → XXXXXXX-VADR
❓ ELT (453-5000-710) []: Não localizado no XLSX → XXXXXXX-ELT
❓ BEACON (DK120) []: Não localizado no XLSX → XXXXXXX-BEACON


sendo que alguns equipamentos, apesar de estarem tanto na planilha xlsx e na seed, 
e com a pos e posicao adequada. por exemplo o adf pn 622-7382-10 esta na planilha 
na posicao TEC e no seed tbm 

na seed os equipamentos sao carregados como
 {"slot": "CMFD4", "equipamento": "CMFD", "pn": "MB387B-01", "loc": "2P", "pos": "MF4"},verifique se essa variavel pos é a do xlsx
 
[COMPORTAMENTO ESPERADO]
- XLSX deve ser processado corretamente na primeira tentativa
- Novos uploads devem funcionar sem necessidade de recarregar página
- Token CSRF deve permanecer válido durante o fluxo

[REPRODUÇÃO]
1. Abrir Configurações  
2. Selecionar “Carregamento Inventário (XLSX)”  
3. Enviar arquivo 5919.xlsx  
4. Observar relatório zerado  
5. Tentar novo upload → erro CSRF / 403

[HIPÓTESE]
- Parser XLSX não está reconhecendo o arquivo/layout
- Fluxo de upload pode estar invalidando ou regenerando incorretamente o token CSRF
- Token CSRF não está sendo atualizado/reutilizado corretamente após falha
- Possível ausência de sincronização entre cookie e header CSRF

[ANÁLISE CSP]
- Baixa probabilidade de relação com CSP
- Erro indica falha de validação CSRF (403), não bloqueio de política de conteúdo

[RESTRIÇÕES]
- Não remover proteção CSRF
- Não alterar CSP
- Preservar compatibilidade com uploads existentes

[ACEITE]
- XLSX processado corretamente
- Relatório apresenta dados reais processados
- Upload pode ser repetido sem recarregar página
- Sem erro CSRF ou 403
- Fluxo permanece seguro
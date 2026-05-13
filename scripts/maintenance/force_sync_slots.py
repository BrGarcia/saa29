import sqlite3

def run_sync():
    conn = sqlite3.connect('saa29_local.db')
    cursor = conn.cursor()

    mapping = [
        ('066-04031-1622', 'GPS', 'CAD'),
        ('174521-10-01', 'VADR', 'FC'),
        ('251-118-012-012', 'ARTU', 'CEL'),
        ('263-000', 'AMPMIC-1P', 'CAD'),
        ('263-000', 'AMPMIC-2P', 'CAT'),
        ('314-04895-403', 'PIC/NAV', 'P1P'),
        ('34200802-80RB', 'EGIR', 'FC'),
        ('343-001', 'ASP-1P', 'P1P'),
        ('343-001', 'ASP-2P', 'P2P'),
        ('4455-1000-01', 'PDU', 'P1P'),
        ('4456-1000-02', 'UFCP', 'P1P'),
        ('4458-1000-00', 'PSU', 'FC'),
        ('449100-02-01', 'AFDC', 'TEC'),
        ('449300-02-01', 'PA CONTROL', 'TC6'),
        ('453-5000-710', 'ELT', 'FC'),
        ('622-7194-201', 'VOR', 'TEC'),
        ('622-7309-101', 'DME', 'TEC'),
        ('622-7382-101', 'ADF', 'TEC'),
        ('622-9352-004', 'TDR', 'TEC'),
        ('733-0402', 'STICKGRIP-1P', 'CAD'),
        ('733-0402', 'STICKGRIP-2P', 'CAT'),
        ('78-8060-6086-5', 'STORMSCOPE', 'CEL'),
        ('DK120', 'BEACON', 'FC'),
        ('MA902B-02', 'MDP1', 'EL1'),
        ('MA902B-02', 'MDP2', 'EL2'),
        ('MB211E-03', 'DVR', 'CAD'),
        ('MB387B-01', 'CMFD1', 'MF1'),
        ('MB387B-01', 'CMFD2', 'MF2'),
        ('MB387B-01', 'CMFD3', 'MF3'),
        ('MB387B-01', 'CMFD4', 'MF4'),
        ('VEC00054', 'CHVC', 'P1P')
    ]

    for pn, slot, pos in mapping:
        cursor.execute("SELECT id FROM modelos_equipamento WHERE part_number = ?", (pn,))
        row = cursor.fetchone()
        if row:
            m_id = row[0]
            cursor.execute("UPDATE slots_inventario SET posicao_xlsx = ? WHERE modelo_id = ? AND nome_posicao = ?", (pos, m_id, slot))
            if cursor.rowcount > 0:
                print(f"OK: {pn} / {slot} -> {pos}")
            else:
                print(f"FAIL: {pn} / {slot} (not found)")
        else:
            print(f"PN NOT FOUND: {pn}")

    conn.commit()
    conn.close()

if __name__ == '__main__':
    run_sync()

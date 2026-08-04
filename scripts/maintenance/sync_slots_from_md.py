import sqlite3

def update_slots():
    conn = sqlite3.connect('saa29_local.db')
    cursor = conn.cursor()

    try:
        with open('docs/mapeamento_posicao_eqp.md', 'r') as f:
            lines = f.readlines()

        # Encontrar a tabela (pula cabeçalho e separador)
        table_lines = [l.strip() for l in lines if l.strip().startswith('|') and 'Part Number' not in l and ':---' not in l]

        updated_count = 0
        for line in table_lines:
            # | PN | Equipamento | Slot | Código XLSX | Status |
            parts = [p.strip() for p in line.split('|')]
            if len(parts) < 5: continue
            
            pn = parts[1]
            slot_nome = parts[3]
            pos_xlsx = parts[4]

            if '*' in pos_xlsx or not pos_xlsx:
                pos_xlsx = None
            elif ',' in pos_xlsx:
                # Caso de múltiplas posições (ex: CMFD), o usuário precisa definir ou o sistema pula
                # Por enquanto vamos manter o que estiver lá ou pular se for ambíguo
                continue

            # Buscar o modelo_id pelo PN
            cursor.execute("SELECT id FROM modelos_equipamento WHERE part_number = ?", (pn,))
            modelo = cursor.fetchone()
            if not modelo: continue
            modelo_id = modelo[0]

            # Atualizar o slot específico desse modelo
            cursor.execute("""
                UPDATE slots_inventario 
                SET posicao_xlsx = ? 
                WHERE modelo_id = ? AND nome_posicao = ?
            """, (pos_xlsx, modelo_id, slot_nome))
            
            if cursor.rowcount > 0:
                updated_count += cursor.rowcount
                print(f"Atualizado: {pn} -> {slot_nome}: {pos_xlsx}")

        conn.commit()
        print(f"\nTotal de slots atualizados: {updated_count}")

    except Exception as e:
        print(f"Erro: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    update_slots()

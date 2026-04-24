/**
 * Scripts para a página de configurações.
 * Por enquanto serve de stub para as funcionalidades futuras.
 */

document.addEventListener("DOMContentLoaded", () => {
    // Verificação extra de segurança no frontend
    const userJson = localStorage.getItem("saa29_user");
    if (userJson) {
        try {
            const user = JSON.parse(userJson);
            const funcao = user.funcao ? user.funcao.toUpperCase() : '';
            if (funcao !== 'ADMINISTRADOR' && funcao !== 'ENCARREGADO') {
                showToast("Acesso Negado: Apenas administradores e encarregados podem acessar esta área.", "error");
                setTimeout(() => {
                    window.location.href = "/panes";
                }, 2000);
            }
        } catch (e) {
            window.location.href = "/panes";
        }
    } else {
        window.location.href = "/login";
    }

    const btnNova = document.getElementById('btn-nova-aeronave');
    if(btnNova) btnNova.onclick = openModalConfig;
    
    const form = document.getElementById('formAeronave');
    if(form) form.addEventListener('submit', criarAeronave);

    const btnDesativar = document.getElementById('btn-desativar-aeronave');
    if(btnDesativar) btnDesativar.onclick = openModalDesativar;
    
    const formDesativar = document.getElementById('formDesativarAeronave');
    if(formDesativar) formDesativar.addEventListener('submit', desativarAeronave);

    const btnReativar = document.getElementById('btn-reativar-aeronave');
    if(btnReativar) btnReativar.onclick = openModalReativar;
    
    const formReativar = document.getElementById('formReativarAeronave');
    if(formReativar) formReativar.addEventListener('submit', reativarAeronave);
});

function openModalConfig() {
    document.querySelector("#modal-aeronave h3").innerText = "Nova Aeronave";
    document.getElementById("btnSalvarAcft").innerText = "Registrar";
    document.getElementById("statusInput").value = "OPERACIONAL";
    document.getElementById("statusInput").disabled = false;
    document.getElementById("modal-aeronave").style.display = "flex";
}

function closeModalConfig() {
    document.getElementById("modal-aeronave").style.display = "none";
    document.getElementById("formAeronave").reset();
}

async function criarAeronave(e) {
    e.preventDefault();
    const btn = document.getElementById("btnSalvarAcft");
    btn.disabled = true;
    
    const matricula = document.getElementById("matriculaInput").value.trim().toUpperCase();
    const sn = document.getElementById("snInput").value.trim();
    const status = document.getElementById("statusInput").value;

    try {
        // Verificar se já existe a matrícula antes de salvar
        const existentes = await apiFetch(`/aeronaves/?limit=1000&incluir_inativas=true`);
        const jaExiste = existentes.some(a => a.matricula === matricula);
        
        if (jaExiste) {
            showToast(`A matrícula ${matricula} já está cadastrada no sistema.`, "error");
            btn.disabled = false;
            return;
        }

        await apiFetch("/aeronaves/", {
            method: "POST",
            body: {
                matricula: matricula,
                serial_number: sn,
                status: status
            }
        });
        showToast("Aeronave cadastrada com sucesso!", "success");
        closeModalConfig();
    } catch(err) {
        showToast(err.message || "Erro ao cadastrar aeronave.", "error");
    } finally {
        btn.disabled = false;
    }
}

window.openModalConfig = openModalConfig;
window.closeModalConfig = closeModalConfig;

async function openModalDesativar() {
    document.getElementById("modal-desativar-aeronave").style.display = "flex";
    const select = document.getElementById("aeronaveDesativarSelect");
    select.innerHTML = '<option value="" disabled selected>Carregando...</option>';
    
    try {
        const aeronaves = await apiFetch(`/aeronaves/?limit=1000`);
        const ativas = aeronaves.filter(a => a.status !== "INATIVA");
        
        if (ativas.length === 0) {
            select.innerHTML = '<option value="" disabled selected>Nenhuma aeronave ativa encontrada.</option>';
        } else {
            select.innerHTML = '<option value="" disabled selected>Selecione uma matrícula</option>';
            ativas.forEach(a => {
                const opt = document.createElement("option");
                opt.value = a.id;
                opt.text = `${a.matricula} (${a.status})`;
                select.appendChild(opt);
            });
        }
    } catch (e) {
        select.innerHTML = '<option value="" disabled selected>Erro ao carregar aeronaves</option>';
    }
}

function closeModalDesativar() {
    document.getElementById("modal-desativar-aeronave").style.display = "none";
    document.getElementById("formDesativarAeronave").reset();
}

async function desativarAeronave(e) {
    e.preventDefault();
    const btn = document.getElementById("btnConfirmarDesativar");
    const select = document.getElementById("aeronaveDesativarSelect");
    const aeronaveId = select.value;
    
    if (!aeronaveId) {
        showToast("Selecione uma aeronave.", "error");
        return;
    }

    const matricula = select.options[select.selectedIndex].text.split(' ')[0];
    
    if (!confirm(`Tem certeza que deseja desativar a aeronave ${matricula}?`)) {
        return;
    }
    
    btn.disabled = true;
    
    try {
        await apiFetch(`/aeronaves/${aeronaveId}/toggle-status`, { method: "POST" });
        showToast("Aeronave desativada com sucesso!", "success");
        closeModalDesativar();
    } catch(err) {
        showToast(err.message || "Erro ao desativar aeronave.", "error");
    } finally {
        btn.disabled = false;
    }
}

window.openModalDesativar = openModalDesativar;
window.closeModalDesativar = closeModalDesativar;

async function openModalReativar() {
    document.getElementById("modal-reativar-aeronave").style.display = "flex";
    const select = document.getElementById("aeronaveReativarSelect");
    select.innerHTML = '<option value="" disabled selected>Carregando...</option>';
    
    try {
        const aeronaves = await apiFetch(`/aeronaves/?limit=1000&incluir_inativas=true`);
        const inativas = aeronaves.filter(a => a.status === "INATIVA");
        
        if (inativas.length === 0) {
            select.innerHTML = '<option value="" disabled selected>Nenhuma aeronave inativa encontrada.</option>';
        } else {
            select.innerHTML = '<option value="" disabled selected>Selecione uma matrícula</option>';
            inativas.forEach(a => {
                const opt = document.createElement("option");
                opt.value = a.id;
                opt.text = `${a.matricula} (${a.status})`;
                select.appendChild(opt);
            });
        }
    } catch (e) {
        select.innerHTML = '<option value="" disabled selected>Erro ao carregar aeronaves</option>';
    }
}

function closeModalReativar() {
    document.getElementById("modal-reativar-aeronave").style.display = "none";
    document.getElementById("formReativarAeronave").reset();
}

async function reativarAeronave(e) {
    e.preventDefault();
    const btn = document.getElementById("btnConfirmarReativar");
    const select = document.getElementById("aeronaveReativarSelect");
    const aeronaveId = select.value;
    
    if (!aeronaveId) {
        showToast("Selecione uma aeronave.", "error");
        return;
    }

    const matricula = select.options[select.selectedIndex].text.split(' ')[0];
    
    if (!confirm(`Tem certeza que deseja reativar a aeronave ${matricula}?`)) {
        return;
    }
    
    btn.disabled = true;
    
    try {
        await apiFetch(`/aeronaves/${aeronaveId}/toggle-status`, { method: "POST" });
        showToast("Aeronave reativada com sucesso!", "success");
        closeModalReativar();
    } catch(err) {
        showToast(err.message || "Erro ao reativar aeronave.", "error");
    } finally {
        btn.disabled = false;
    }
}

window.openModalReativar = openModalReativar;
window.closeModalReativar = closeModalReativar;

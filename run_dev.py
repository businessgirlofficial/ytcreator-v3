"""
run_dev.py - Levanta TODOS los microservicios de agentes a la vez.
=====================================================================

Uso:
    python run_dev.py

Presiona Ctrl+C para apagar todos los servicios juntos.

Esto es solo para desarrollo/pruebas locales. Cada agente sigue
siendo un proceso independiente (microservicio real) - este script
simplemente te ahorra abrir 16 terminales distintas.
"""

import subprocess
import sys
import time
from pathlib import Path

GRACEFUL_TIMEOUT = 10

BASE = Path(__file__).resolve().parent

# Orden sugerido: no es obligatorio (cada servicio es independiente y
# escucha en su propio puerto), pero asi se ve agrupado por departamento.
SERVICIOS = [
    # Depto 0 - Inteligencia de Canal
    BASE / "agents" / "agent_0_1_escaner_canal" / "main.py",
    BASE / "agents" / "agent_0_2_analizador_canal" / "main.py",
    BASE / "agents" / "agent_0_3_monitor_mercado" / "main.py",
    BASE / "agents" / "agent_0_4_asesor_estrategico" / "main.py",
    BASE / "agents" / "agent_0_5_tracker_performance" / "main.py",
    BASE / "orchestrator" / "sub_orq_inteligencia" / "main.py",
    # Depto 1 - Estrategia
    BASE / "agents" / "agent_1_1_investigador" / "main.py",
    BASE / "agents" / "agent_1_2_copywriter" / "main.py",
    BASE / "agents" / "agent_1_3_director_arte" / "main.py",
    BASE / "agents" / "agent_1_4_generador_miniatura" / "main.py",
    BASE / "orchestrator" / "sub_orq_estrategia" / "main.py",
    BASE / "agents" / "agent_2_1_guionista" / "main.py",
    BASE / "orchestrator" / "sub_orq_guion" / "main.py",
    BASE / "agents" / "agent_3_1_prompt_maker" / "main.py",
    BASE / "agents" / "agent_3_2_generador_visual" / "main.py",
    BASE / "orchestrator" / "sub_orq_visual" / "main.py",
    BASE / "agents" / "agent_4_1_locucion" / "main.py",
    BASE / "agents" / "agent_4_2_musica" / "main.py",
    BASE / "agents" / "agent_4_3_subtitulos" / "main.py",
    BASE / "orchestrator" / "sub_orq_audio" / "main.py",
    BASE / "agents" / "agent_5_1_editor" / "main.py",
    BASE / "agents" / "agent_5_2_seo" / "main.py",
    BASE / "agents" / "agent_5_3_compliance" / "main.py",
    BASE / "agents" / "agent_5_4_policy_monitor" / "main.py",
    BASE / "agents" / "agent_5_5_publicador" / "main.py",
    BASE / "orchestrator" / "sub_orq_cierre" / "main.py",
    BASE / "orchestrator" / "main.py",
    # Gateway — proxy unico para Streamlit (puerto 7861)
    BASE / "gateway.py",
]


def main():
    procesos = []
    print(f"Levantando {len(SERVICIOS)} microservicios...\n")
    for script in SERVICIOS:
        if not script.exists():
            print(f"  [SKIP] no encontrado: {script}")
            continue
        p = subprocess.Popen([sys.executable, str(script)], cwd=str(BASE))
        procesos.append(p)
        print(f"  [OK] {script.parent.name} (PID {p.pid})")
        time.sleep(0.3)

    print(f"\nTodos los servicios corriendo. Ctrl+C para apagar (graceful), doble Ctrl+C para forzar.\n")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print(f"\nCtrl+C recibido. Los hijos reciben la señal automaticamente.")
        print(f"Esperando {GRACEFUL_TIMEOUT}s a que terminen...")

        inicio = time.time()
        try:
            while time.time() - inicio < GRACEFUL_TIMEOUT:
                vivos = [p for p in procesos if p.poll() is None]
                if not vivos:
                    print("Todos los servicios terminaron limpiamente.")
                    return
                time.sleep(0.5)

            vivos = [p for p in procesos if p.poll() is None]
            if vivos:
                print(f"{len(vivos)} servicios no respondieron, enviando terminate...")
                for p in vivos:
                    p.terminate()
        except KeyboardInterrupt:
            print("\nDoble Ctrl+C: forzando cierre inmediato...")
            for p in procesos:
                if p.poll() is None:
                    p.terminate()


if __name__ == "__main__":
    main()

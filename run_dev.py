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

BASE = Path(__file__).resolve().parent

# Orden sugerido: no es obligatorio (cada servicio es independiente y
# escucha en su propio puerto), pero asi se ve agrupado por departamento.
SERVICIOS = [
    BASE / "agents" / "agent_1_1_investigador" / "main.py",
    BASE / "agents" / "agent_1_2_copywriter" / "main.py",
    BASE / "agents" / "agent_1_3_director_arte" / "main.py",
    BASE / "agents" / "agent_1_4_generador_miniatura" / "main.py",
    BASE / "orchestrator" / "sub_orq_estrategia" / "main.py",
    BASE / "agents" / "agent_2_1_guionista" / "main.py",
    BASE / "agents" / "agent_2_2_evaluador" / "main.py",
    BASE / "agents" / "agent_3_1_prompt_maker" / "main.py",
    BASE / "agents" / "agent_3_2_generador_visual" / "main.py",
    BASE / "agents" / "agent_4_1_locucion" / "main.py",
    BASE / "agents" / "agent_4_2_musica" / "main.py",
    BASE / "agents" / "agent_4_3_subtitulos" / "main.py",
    BASE / "orchestrator" / "sub_orq_audio" / "main.py",
    BASE / "agents" / "agent_5_1_editor" / "main.py",
    BASE / "agents" / "agent_5_2_seo" / "main.py",
    BASE / "orchestrator" / "sub_orq_cierre" / "main.py",
    BASE / "orchestrator" / "main.py",
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

    print("\nTodos los servicios corriendo. Ctrl+C para apagar.\n")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nApagando todos los servicios...")
        for p in procesos:
            p.terminate()


if __name__ == "__main__":
    main()

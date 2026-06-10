#!/usr/bin/env python3
import sys
import os
import ast

def check_syntax(file_path):
    """Verifica se o arquivo Python possui erros de sintaxe."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        ast.parse(content, filename=file_path)
        return True, ""
    except SyntaxError as e:
        return False, f"Linha {e.lineno}, Coluna {e.offset}: {e.msg}"
    except Exception as e:
        return False, str(e)

def check_conflict_markers(file_path):
    """Verifica se há marcadores de conflito do Git no arquivo."""
    # Excluir arquivos markdown e de documentação que possam citar os marcadores intencionalmente
    if file_path.endswith("GOVERNANCE.md") or file_path.endswith("SECURITY.md") or file_path.endswith("verify.py"):
        return True, []
        
    found = []
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            for idx, line in enumerate(f, 1):
                stripped = line.strip()
                # <<<<<<< HEAD or <<<<<<< branch_name
                if stripped.startswith("<<<<<<<"):
                    found.append((idx, "<<<<<<<"))
                # ======= exactly
                elif stripped == "=======":
                    found.append((idx, "======="))
                # >>>>>>> branch_name
                elif stripped.startswith(">>>>>>>"):
                    found.append((idx, ">>>>>>>"))
    except Exception as e:
        return False, [f"Erro de leitura: {e}"]
        
    return len(found) == 0, found

def main():
    print("=" * 60)
    print("VIGILIA - PIPELINE DE VALIDACAO LOCAL & SANIDADE")
    print("=" * 60)
    
    root_dir = os.path.dirname(os.path.abspath(__file__))
    failed = False
    
    python_files = []
    other_files = []
    
    exclude_dirs = [
        ".git", ".venv", "venv", "__pycache__", ".devcontainer",
        "node_modules", ".firebase", "scratch",
    ]
    
    for root, dirs, files in os.walk(root_dir):
        # Ignorar pastas desnecessárias
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for file in files:
            path = os.path.join(root, file)
            if file.endswith(".py"):
                python_files.append(path)
            elif file.endswith((".css", ".html", ".js", ".json")):
                other_files.append(path)

    print(f"Encontrados {len(python_files)} arquivos Python e {len(other_files)} outros arquivos relevantes para verificar.\n")
    
    # 1. Verificar Sintaxe Python
    print("[1/2] Verificando sintaxe dos arquivos Python...")
    syntax_errors = 0
    for file_path in python_files:
        rel_path = os.path.relpath(file_path, root_dir)
        ok, err = check_syntax(file_path)
        if not ok:
            print(f"[ERRO DE SINTAXE] em {rel_path}:")
            print(f"   -> {err}")
            syntax_errors += 1
            failed = True
        else:
            print(f"  [OK] {rel_path}: Sintaxe OK")
            
    if syntax_errors == 0:
        print("[SUCESSO] Todos os arquivos Python possuem sintaxe valida!\n")
    else:
        print(f"[AVISO] Encontrados {syntax_errors} erros de sintaxe.\n")

    # 2. Verificar Marcadores de Conflito
    print("[2/2] Verificando marcadores de conflito do Git...")
    conflict_errors = 0
    all_files = python_files + other_files
    for file_path in all_files:
        rel_path = os.path.relpath(file_path, root_dir)
        ok, markers = check_conflict_markers(file_path)
        if not ok:
            print(f"[CONFLITO DE MERGE] detectado em {rel_path}:")
            for line_no, marker in markers:
                print(f"   -> Linha {line_no}: Marcador '{marker}'")
            conflict_errors += 1
            failed = True
            
    if conflict_errors == 0:
        print("[SUCESSO] Nenhum marcador de conflito Git encontrado!\n")
    else:
        print(f"[AVISO] Encontrados {conflict_errors} arquivos com marcadores de conflito.\n")

    print("=" * 60)
    if failed:
        print("[FALHA] VALIDACAO FALHOU! Corrija os erros listados acima.")
        print("=" * 60)
        sys.exit(1)
    else:
        print("[SUCESSO] VALIDACAO CONCLUIDA COM SUCESSO! O codigo esta limpo e pronto.")
        print("=" * 60)
        sys.exit(0)

if __name__ == "__main__":
    main()

"""Aplica somente os pontos de entrada da aba à versão atual de index.html."""
import argparse
import difflib
from pathlib import Path

CHANGES = [
('<meta name="color-scheme" content="light dark">', '<meta name="color-scheme" content="light dark">\n<link rel="stylesheet" href="concorrentes.css?v=20260908-dates">'),
('    <button role="tab" data-tab="forn" aria-selected="false">Fornecedores</button>', '    <button role="tab" data-tab="forn" aria-selected="false">Fornecedores</button>\n    <button role="tab" data-tab="conc" aria-selected="false" aria-controls="tab-conc">Concorrentes</button>'),
('<!-- ================= SHOPEE ================= -->', '<!-- ================= SHOPEE ================= -->\n<section id="tab-conc" hidden aria-label="Concorrentes">\n  <div id="conc-root"><p role="status">Carregando concorrentes…</p></div>\n</section>\n'),
('<script>', '<script src="concorrentes.js?v=20260908-dates"></script>\n<script>'),
("  if (t==='forn') setTimeout(fornLoad, 0);", "  if (t==='forn') setTimeout(fornLoad, 0);\n  if (t==='conc') setTimeout(()=>window.RadarConcorrentes.load(), 0);\n  else if(location.hash.startsWith('#concorrentes')) history.replaceState(null,'',location.pathname+location.search);"),
("try{ const t=localStorage.getItem('radar.tab'); if(t && $('#tab-'+t)) showTab(t);}catch(e){}", "try{ const t=location.hash.startsWith('#concorrentes') ? 'conc' : localStorage.getItem('radar.tab'); if(t && $('#tab-'+t)) showTab(t);}catch(e){}"),
]

def integrate(source):
    if 'src="concorrentes.js?' in source:
        raise ValueError("A aba já está integrada; não reaplicar o patch.")
    out=source
    for before,after in CHANGES:
        if out.count(before)!=1:
            raise ValueError("Ponto de integração ambíguo ou ausente: "+before[:90])
        out=out.replace(before,after,1)
    return out

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('source',type=Path)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    original=args.source.read_text(encoding='utf-8-sig')
    updated=integrate(original)
    args.output.write_text(updated,encoding='utf-8')
    print(''.join(difflib.unified_diff(original.splitlines(True),updated.splitlines(True),fromfile=str(args.source),tofile=str(args.output))))

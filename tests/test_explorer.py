"""The interactive network explorer.

The page does its own inference in JavaScript, so the most important check is
that its posteriors agree with pyAgrum's. That test needs Node.js and is
skipped without it.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess

import numpy as np
import pytest

from layerbn.explorer import explorer_html, explorer_model


@pytest.fixture(scope="module")
def model(study):
    return explorer_model(study)


def test_the_model_holds_every_variable_and_arc_of_the_network(study, model):
    bn = study.network()
    assert {n["id"] for n in model["nodes"]} == set(bn.names())
    assert {(a["from"], a["to"]) for a in model["arcs"]} == set(study.arcs())
    assert any(n["target"] for n in model["nodes"])


def test_every_cpt_row_is_a_distribution(model):
    by_id = {n["id"]: n for n in model["nodes"]}
    for node in model["nodes"]:
        rows = int(np.prod([len(by_id[p]["states"]) for p in node["parents"]]))
        table = np.array(node["cpt"]).reshape(rows, len(node["states"]))
        assert np.allclose(table.sum(axis=1), 1, atol=1e-5), node["id"]


def test_the_page_is_self_contained_and_carries_the_data(model):
    html = explorer_html(model)
    assert "__DATA__" not in html and "__TITLE__" not in html
    assert "src=\"http" not in html and "href=\"http" not in html
    data = json.loads(re.search(r"const M = (.*?);\nconst MISS", html, re.S).group(1)
                      .replace("<\\/", "</"))
    assert data["nodes"] == model["nodes"]


def test_text_cannot_break_out_of_the_page(model):
    hostile = dict(model, title="<b>x</b>", subtitle="</script><script>alert(1)</script>")
    html = explorer_html(hostile)
    assert "<b>x</b>" not in html
    assert html.count("</script>") == 1


def test_starting_evidence_is_written_into_the_page(model):
    node = model["nodes"][0]
    html = explorer_html(model, {node["id"]: node["states"][0]})
    assert json.dumps({node["id"]: [node["states"][0]]}, ensure_ascii=False)[1:-1] in html


def test_the_study_can_save_an_explorer(study, tmp_path):
    page = study.explore(path=tmp_path / "net.html")
    assert (tmp_path / "net.html").read_text(encoding="utf-8") == page.html
    assert "<iframe srcdoc=" in page._repr_html_()


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_the_pages_inference_agrees_with_pyagrum(study, model):
    import pyagrum as gum

    html = explorer_html(model)
    script = html.split("<script>\n", 1)[1]
    engine = script[script.index("const byId"):script.index("function compute")]
    engine = engine.replace("let evidence = {};", "let evidence = {}; void evidence;")

    bn = study.network()
    nodes = {n["id"]: n for n in model["nodes"]}
    ids = list(nodes)
    rng = np.random.default_rng(1)
    cases = [{}]
    for _ in range(6):                      # hard and "one of these states" evidence
        chosen = rng.choice(ids, size=2, replace=False)
        case = {}
        for i, v in enumerate(chosen):
            k = len(nodes[v]["states"])
            states = [int(rng.integers(k))] if i == 0 else sorted(
                set(rng.choice(k, size=min(2, k), replace=False).tolist()))
            case[v] = states
        cases.append(case)

    program = (f"const M = {json.dumps(model, allow_nan=False, default=lambda o: None)};\n"
               + engine
               + f"const cases = {json.dumps(cases)};\n"
               "const out = cases.map(c => { const ev = {};"
               " for (const k in c) ev[k] = new Set(c[k]);"
               " return Object.fromEntries(M.nodes.map(n => [n.id, query(n.id, ev).p])); });\n"
               "process.stdout.write(JSON.stringify(out));\n")
    result = subprocess.run(["node", "-e", program], capture_output=True, text=True,
                            timeout=120, check=True)
    page = json.loads(result.stdout)

    for case, posteriors in zip(cases, page, strict=True):
        ie = gum.LazyPropagation(bn)
        for v, states in case.items():
            likelihood = [0.0] * len(nodes[v]["states"])
            for s in states:
                likelihood[s] = 1.0
            ie.addEvidence(v, likelihood)
        ie.makeInference()
        for v in ids:
            expected = ie.posterior(v).toarray()
            assert np.allclose(posteriors[v], expected, atol=1e-4), (case, v)

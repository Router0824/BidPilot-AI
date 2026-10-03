"""Literal Word placeholders; no template expressions or executable syntax."""
import re
from docx.oxml.ns import qn

TOKENS = {"{{project_name}}", "{{company_name}}", "{{content}}"}


def paragraphs(document):
    roots = [document.element]
    roots.extend(part.element for part in document.part.related_parts.values()
                 if str(part.partname).startswith(("/word/header", "/word/footer")))
    for root in roots:
        yield from root.iter(qn("w:p"))


def paragraph_text(paragraph):
    return "".join(node.text or "" for node in paragraph.iter(qn("w:t")))


def inspect_template(document):
    found = []
    anchors = []
    for paragraph in paragraphs(document):
        text = paragraph_text(paragraph)
        for match in re.finditer(r"\{\{[^{}]+\}\}", text):
            token = match.group()
            if token not in TOKENS:
                raise ValueError(f"不支持的模板字段：{token}")
            found.append(token)
            if token == "{{content}}":
                if paragraph.getparent() is not document.element.body or text.strip() != token:
                    raise ValueError("正文占位符 {{content}} 必须独占正文中的一个段落，不能位于表格或页眉页脚")
                anchors.append(paragraph)
    if len(anchors) > 1:
        raise ValueError("模板只能包含一个 {{content}} 正文占位符")
    return {"fields": sorted(set(found)), "insertion": "placeholder" if anchors else "append"}


def fill_template(document, project_name, company_name):
    info = inspect_template(document)
    if "{{company_name}}" in info["fields"] and not company_name.strip():
        raise ValueError("模板使用了投标单位字段，请先填写投标单位")
    values = {"{{project_name}}": project_name, "{{company_name}}": company_name}
    anchor = None
    for paragraph in paragraphs(document):
        nodes = list(paragraph.iter(qn("w:t")))
        text = paragraph_text(paragraph)
        if text.strip() == "{{content}}":
            anchor = paragraph
        offsets, offset = [], 0
        for node in nodes:
            offsets.append(offset)
            offset += len(node.text or "")
        # Work backwards so offsets remain valid for earlier placeholders.
        for match in reversed(list(re.finditer(r"\{\{(?:project_name|company_name)\}\}", text))):
            first = next(i for i, node in enumerate(nodes) if offsets[i] + len(node.text or "") > match.start())
            last = next(i for i, node in enumerate(nodes) if offsets[i] + len(node.text or "") >= match.end())
            prefix = (nodes[first].text or "")[:match.start() - offsets[first]]
            suffix = (nodes[last].text or "")[match.end() - offsets[last]:]
            nodes[first].text = prefix + values[match.group()] + (suffix if first == last else "")
            nodes[first].set(qn("xml:space"), "preserve")
            if first != last:
                for node in nodes[first + 1:last]:
                    node.text = ""
                nodes[last].text = suffix
                nodes[last].set(qn("xml:space"), "preserve")
    return info, anchor

from mkdocs.config import config_options, Config
from mkdocs.plugins import BasePlugin
from mkdocs.structure.files import Files, File
from mkdocs.structure.pages import Page
from mkdocs.commands.build import _populate_page, _build_page

import re
import os
import sys
import json
import uuid
import urllib
import requests

import cromulent
from cromulent import model, vocab
from cromulent.model import factory
from collections import OrderedDict

vocab.add_art_setter()
vocab.add_attribute_assignment_check()
vocab.conceptual_only_parts()
vocab.set_linked_art_uri_segments()


class LinkedArtPlugin(BasePlugin):
    config_scheme = (
        ("baseUrl", config_options.Type(str, default="https://linked.art/example/")),
        ("baseDir", config_options.Type(str, default="docs/example")),
        (
            "contextUrl",
            config_options.Type(
                str, default="https://linked.art/ns/v1/linked-art.json"
            ),
        ),
        ("autoIdType", config_options.Type(str, default="int-per-segment")),
        ("linkAAT", config_options.Type(bool, default=True)),
    )

    def __init__(self):
        self.enabled = True
        self.total_time = 0
        factory.id_type_label = True
        factory.auto_assign_id = False
        self.aat_labels = {}

        self.aat_re = re.compile("aat:([0-9]+)")
        self.ctxt_eg_re = re.compile('(?<!`)(&quot;|")([0-9A-Za-z_|:]+)(&quot;|")')
        self.ctxt_text_re = re.compile("`([A-Za-z_]+)`")
        self.context = factory.context_json["@context"]

        self.class_styles = {
            "HumanMadeObject": "object",
            "Place": "place",
            "Actor": "actor",
            "Person": "actor",
            "Group": "actor",
            "Type": "type",
            "MeasurementUnit": "type",
            "Currency": "type",
            "Material": "type",
            "Language": "type",
            "Name": "name",
            "Identifier": "name",
            "Dimension": "dims",
            "MonetaryAmount": "dims",
            "LinguisticObject": "infoobj",
            "VisualItem": "infoobj",
            "InformationObject": "infoobj",
            "Set": "infoobj",
            "PropositionalObject": "infoobj",
            "Right": "infoobj",
            "PropertyInterest": "infoobj",
            "TimeSpan": "timespan",
            "Activity": "event",
            "Event": "event",
            "Period": "event",
            "Birth": "event",
            "Death": "event",
            "Production": "event",
            "Destruction": "event",
            "Creation": "event",
            "Formation": "event",
            "Dissolution": "event",
            "Acquisition": "event",
            "TransferOfCustody": "event",
            "Move": "event",
            "Payment": "event",
            "AttributeAssignment": "event",
            "Phase": "event",
            "RightAcquisition": "event",
            "PartRemoval": "event",
            "PartAddition": "event",
            "Encounter": "event",
            "Modification": "event",
            "DigitalObject": "digital",
            "DigitalService": "digital",
            "Addition": "event",
            "Removal": "event",
            "Transfer": "event",
        }

    def on_pre_build(self, config):
        factory.base_url = self.config["baseUrl"]
        factory.auto_id_type = self.config["autoIdType"]
        factory.base_dir = self.config["baseDir"]
        self.nav_cache = None
        self.env_cache = None

        if self.config["linkAAT"]:
            fh = open("scripts/aat_labels.json")
            data = fh.read()
            fh.close()
            self.aat_labels = json.loads(data)

        fn = os.path.join(os.path.dirname(cromulent.__file__), "data")
        fn += "/crm-profile.json"
        fh = open(fn)
        d = fh.read()
        fh.close()
        self.linked_art_profile = json.loads(d)

    def generate_example(self, code, page):
        code = "global top\nfrom cromulent import model, vocab\n" + code
        try:
            exec(code)
        except Exception as e:
            print(f">>> In {page}, got: {e}")
            print(code)
            raise

        factory.pipe_scoped_contexts = False
        factory.toFile(top, compact=False)
        js = factory.toJSON(top)
        factory.pipe_scoped_contexts = True
        jsstr = factory.toHtml(top)
        factory.pipe_scoped_contexts = False

        # Generate other syntaxes, now in crom
        ttl = factory.toFile(top, format="ttl", extension=".ttl")
        mmd = self.build_mermaid(js)
        # self.traverse(js, top.id, page)

        raw = top.id
        jsuri = raw + ".json"
        rawq = urllib.parse.quote(raw).replace("/", "%2F")
        playground = (
            "http://json-ld.org/playground-dev/#startTab=tab-expanded&copyContext=true&json-ld=%s"
            % jsuri
        )
        turtle = raw + ".ttl"
        turtle_play = "https://niklasl.github.io/ldtr/demo/?edit=true&url=%s" % turtle
        links = f"[JSON-LD (raw)]({raw}) | [JSON-LD (playground)]({playground}) | [Turtle (raw)]({turtle}) | [Turtle (styled)]({turtle_play})"

        return f"{jsstr}\n```mermaid\n{mmd}\n```\nOther Representations: {links}"

    def build_mermaid(self, js):
        curr_int = 1
        mermaid = []
        id_map = {}
        mermaid.append("graph TD")
        mermaid.append("classDef object stroke:black,fill:#E1BA9C,rx:20px,ry:20px;")
        mermaid.append("classDef actor stroke:black,fill:#FFBDCA,rx:20px,ry:20px;")
        mermaid.append("classDef type stroke:red,fill:#FAB565,rx:20px,ry:20px;")
        mermaid.append("classDef name stroke:orange,fill:#FEF3BA,rx:20px,ry:20px;")
        mermaid.append("classDef dims stroke:black,fill:#c6c6c6,rx:20px,ry:20px;")
        mermaid.append("classDef infoobj stroke:#907010,fill:#fffa40,rx:20px,ry:20px")
        mermaid.append("classDef timespan stroke:blue,fill:#ddfffe,rx:20px,ry:20px")
        mermaid.append("classDef place stroke:#3a7a3a,fill:#aff090,rx:20px,ry:20px")
        mermaid.append("classDef event stroke:#1010FF,fill:#96e0f6,rx:20px,ry:20px")
        mermaid.append("classDef literal stroke:black,fill:#f0f0e0;")
        mermaid.append("classDef classstyle stroke:black,fill:white;")
        self.walk(js, curr_int, id_map, mermaid)
        return "\n".join(mermaid)

    def uri_to_label(self, uri):
        if uri.startswith("http://vocab.getty.edu/"):
            uri = uri.replace("http://vocab.getty.edu/", "")
            uri = uri.replace("/", ":")
        elif uri.startswith("https://linked.art/example/"):
            uri = uri.replace("https://linked.art/example/", "")
            # uri = uri.replace('/', '')
        elif uri.startswith("http://qudt.org/1.1/vocab/unit/"):
            uri = uri.replace("http://qudt.org/1.1/vocab/unit/", "qudt:")
        else:
            # print("Unhandled URI: %s" % uri)
            pass
        return uri

    def walk(self, js, curr_int, id_map, mermaid):
        if isinstance(js, dict) or isinstance(js, OrderedDict):
            # Resource
            if "id" in js:
                curr = js["id"]
                lbl = self.uri_to_label(curr)
            else:
                curr = str(uuid.uuid4())
                lbl = " _ "
            if curr in id_map:
                currid = id_map[curr]
            else:
                currid = "O%s" % curr_int
                curr_int += 1
                id_map[curr] = currid
            line = "%s(%s)" % (currid, lbl)
            if not line in mermaid:
                mermaid.append(line)
            t = js.get("type", "")
            if t:
                style = self.class_styles.get(t, "")
                if style:
                    line = "class %s %s;" % (currid, style)
                    if not line in mermaid:
                        mermaid.append("class %s %s;" % (currid, style))
                else:
                    print("No style for class %s" % t)
                line = "%s-- type -->%s_0[%s]" % (currid, currid, t)
                if not line in mermaid:
                    mermaid.append(line)
                    mermaid.append("class %s_0 classstyle;" % currid)

            n = 0
            for k, v in js.items():
                n += 1
                if k in ["@context", "id", "type"]:
                    continue
                elif isinstance(v, list):
                    for vi in v:
                        if isinstance(vi, dict) or isinstance(vi, OrderedDict):
                            (rng, curr_int, id_map) = self.walk(
                                vi, curr_int, id_map, mermaid
                            )
                            mermaid.append("%s-- %s -->%s" % (currid, k, rng))
                        else:
                            print("Iterating a list and found %r" % vi)
                elif isinstance(v, dict) or isinstance(v, OrderedDict):
                    (rng, curr_int, id_map) = self.walk(v, curr_int, id_map, mermaid)
                    line = "%s-- %s -->%s" % (currid, k, rng)
                    if not line in mermaid:
                        mermaid.append(line)
                else:
                    if type(v) == str:
                        # :|
                        v = v.replace('"', "&quot;")
                        v = "\"''%s''\"" % v
                    line = "%s-- %s -->%s_%s(%s)" % (currid, k, currid, n, v)
                    if not line in mermaid:
                        mermaid.append(line)
                        mermaid.append("class %s_%s literal;" % (currid, n))
            return (currid, curr_int, id_map)

    def fetch_aat_label(self, what):
        url = what.replace("aat:", "http://vocab.getty.edu/aat/")
        url += ".jsonld"
        try:
            resp = requests.get(url)
            aatjs = json.loads(resp.text)
        except:
            return ""

        if not "identified_by" in aatjs:
            return ""
        names = aatjs["identified_by"]
        for n in names:
            if "classified_as" in n:
                if "http://vocab.getty.edu/term/type/Descriptor" in [
                    x["id"] for x in n["classified_as"] if "id" in x
                ]:
                    if "language" in n and "en" in [
                        x["_label"] for x in n["language"] if "_label" in x
                    ]:
                        label = n["content"]
                        self.aat_labels[what] = label
                        return label
        return ""

    def do_aatlabel(self, source):
        full = source.group(0)
        if not self.config["linkAAT"]:
            return full
        data = source.group(1)
        label = self.aat_labels.get(full) or self.fetch_aat_label(full)
        label = label.replace('"', "")
        return (
            '<a href="http://vocab.getty.edu/aat/%s" data-ot="%s" data-ot-title="AAT Term" data-ot-fixed="true" class="aat">aat:%s</a>'
            % (data, label, data)
        )

    def do_ctxt_eg(self, source):
        full = source.group(0)
        try:
            data = source.group(2)
        except:
            data = full
        return self.do_ctxt_label(full, data)

    def do_ctxt_text(self, source):
        full = source.group(0)
        try:
            data = source.group(1)
        except:
            data = full
        return self.do_ctxt_label(full, data)

    def do_ctxt_label(self, full, data):
        pidx = data.find("|")
        if pidx > -1:
            # Hack to include it in the serialization
            ttl = "Core Linked Data Term"
            col = ""
            crm = data[pidx + 1 :]
            full = full.replace("|%s" % crm, "")
        elif data in self.context:
            # So it's CRM or added extension
            # get the full from
            defn = self.context[data]
            if not type(defn) == dict:
                # type --> @type
                crm = defn
                ttl = "Core Linked Data Term"
                col = ""
            else:
                crm = self.context[data]["@id"]
                term = crm.replace("crm:", "")
                if term in self.linked_art_profile:
                    okay = self.linked_art_profile[term]
                    if okay == 0 or (type(okay) == list and okay[0] == 0):
                        ttl = "Extension Linked Data Term"
                        col = 'style="color: orange"'
                    else:
                        ttl = "Core Linked Data Term"
                        col = ""
                else:
                    return full
        else:
            return full
        val = (
            '<abbr %s data-ot="%s" data-ot-title="%s" data-ot-fixed="true">%s</abbr>'
            % (col, crm, ttl, full)
        )
        return val

    def on_page_markdown(self, markdown, page, config, files):
        # _aat:nnn_ to hyperlink and tooltips
        markdown = self.aat_re.sub(self.do_aatlabel, markdown)

        # Do linked art extension here
        matcher = re.compile("^(```[ ]*crom[ ]*$(.+?)^```)$", re.M | re.U | re.S)
        hits = matcher.findall(markdown)
        for h in hits:
            eg = self.generate_example(h[1], page)
            markdown = markdown.replace(h[0], eg)

            # json-ld context tooltips
            markdown = self.ctxt_eg_re.sub(self.do_ctxt_eg, markdown)
            markdown = self.ctxt_text_re.sub(self.do_ctxt_text, markdown)
        return markdown

    # def on_serve(self, server, config, builder):
    #    return server

    # def on_files(self, files, config):
    #    return files

    def on_nav(self, nav, config, files):
        # Cache the build nav for later
        self.nav_cache = nav
        return nav

    def on_env(self, env, config, files):
        # Cache env for later too
        self.env_cache = env
        return env

    # def on_config(self, config):
    #    return config

    # def on_pre_template(self, template, template_name, config):
    #    return template

    # def on_template_context(self, context, template_name, config):
    #    return context

    # def on_post_template(self, output_content, template_name, config):
    #    return output_content

    # def on_pre_page(self, page, config, files):
    #    return page

    # def on_page_read_source(self, page, config):
    #    return ""

    # def on_page_content(self, html, page, config, files):
    #    return html

    # def on_page_context(self, context, page, config, nav):
    #    return context

    # def on_post_page(self, output_content, page, config):
    #    return output_content

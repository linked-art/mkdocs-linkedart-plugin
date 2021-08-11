from mkdocs.config import config_options, Config
from mkdocs.plugins import BasePlugin

import re

import cromulent
from cromulent import model, vocab
from cromulent.model import factory
from collections import OrderedDict

import uuid
import urllib

vocab.add_art_setter()
vocab.add_attribute_assignment_check()
vocab.conceptual_only_parts()
vocab.set_linked_art_uri_segments()

class LinkedArtPlugin(BasePlugin):

    config_scheme = (
        ('baseUrl', config_options.Type(str, default='https://linked.art/example/')),
        ('baseDir', config_options.Type(str, default='docs/example')),
        ('contextUrl', config_options.Type(str, default='https://linked.art/ns/v1/linked-art.json')),
        ('autoIdType', config_options.Type(str, default='int-per-segment')),
    )

    def __init__(self):
        self.enabled = True
        self.total_time = 0
        factory.id_type_label = True
        factory.auto_assign_id = False
        self.aat_hash = {}
        self.prop_hash = {}
        self.class_hash = {}
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
            "Removal": "event"
        }


    def on_pre_build(self, config):
        factory.base_url = self.config['baseUrl']
        factory.auto_id_type = self.config['autoIdType']
        factory.base_dir = self.config['baseDir']
        self.aat_hash = {}
        self.prop_hash = {}
        self.class_hash = {}

    def on_post_build(self, config):
        # Write the index
        top = """---
title: Index of Classes, Properties, Authorities
---


"""
        lines = [top]
 
        lines.append("## Class Index")
        its = list(self.class_hash.items())
        its.sort()
        for (k,v) in its:
            lines.append("* __`%s`__" % k)
            lv= []
            for (k2,v2) in v.items():
                n = k2.replace('https://linked.art/example/', '')
                lv.append("[%s](%s)" % (n, v2.abs_url + "#" + n.replace('/', '_')))          
            vstr = ' | '.join(lv)
            lines.append("    * %s" % vstr)

        lines.append("\n## Property Index")
        its = list(self.prop_hash.items())
        its.sort()
        for (k,v) in its:
            lines.append("* __`%s`__" % k)
            lv= []
            for (k2,v2) in v.items():
                n = k2.replace('https://linked.art/example/', '')
                lv.append("[%s](%s)" % (n, v2.abs_url + "#" + n.replace('/', '_')))          
            vstr = ' | '.join(lv)
            lines.append("    * %s" % vstr)

        lines.append("\n## AAT Index")
        its = list(self.aat_hash.items())
        its.sort()      
        for (k,v) in its:
            if not k.startswith('aat:'):
                continue
            lines.append("* __%s__: _%s_" % (k, aat_labels.get(k) or fetch_aat_label(k)))
            lv= []
            for (k2,v2) in v.items():
                n = k2.replace('https://linked.art/example/', '')               
                lv.append("[%s](%s)" % (n, v2.abs_url + "#" + n.replace('/', '_')))
            vstr = ' | '.join(lv)
            lines.append("    * %s" % vstr)

        out = '\n'.join(lines)
        fh = open('docs/model/example_index.md', 'w')
        fh.write(out)
        fh.close()

        #fl = File('/model/example_index.md', config['docs_dir'], config['site_dir'], config['use_directory_urls'])


        return

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
        ttl = factory.toFile(top, format='ttl', extension='.ttl')
        mmd = self.build_mermaid(js)
        self.traverse(js, top.id, page)

        raw = top.id
        jsuri = raw + '.json'
        rawq = urllib.parse.quote(raw).replace('/', '%2F')
        playground = "http://json-ld.org/playground-dev/#startTab=tab-expanded&copyContext=true&json-ld=%s" % rawq
        turtle = raw + '.ttl'
        turtle_play = "http://cdn.rawgit.com/niklasl/ldtr/v0.2.2/demo/?edit=true&url=%s" % turtle
        links = f"[JSON-LD (raw)]({raw}) | [JSON-LD (playground)]({playground}) | [Turtle (raw)]({turtle}) | [Turtle (styled)]({turtle_play})]"

        return f"{jsstr}\n```mermaid\n{mmd}\n```\nOther Representations: {links}"


    def traverse(self, what, top, page):
        for (k,v) in what.items():
            if k == 'type':
                which = "class_hash"
                nv = v
            elif k == 'classified_as':
                which = "aat_hash"
                nv = v
            elif k == 'id':
                if v.startswith('aat:'):
                    which = "aat_hash"
                    nv = v
                else:
                    continue
            elif k == '@context':
                continue
            else:
                which = "prop_hash"         
                nv = k

            h = getattr(self, which)
            if type(nv) == list:
                for t in nv:
                    if type(t) == dict or isinstance(t, OrderedDict):
                        t = t['id'] 
                    try:
                        h[t][top] = page
                    except:
                        h[t] = {top: page}
            else:   
                if type(nv) == dict or isinstance(nv, OrderedDict):
                    nv = nv['id']
                try:
                    h[nv][top] = page
                except:
                    h[nv] = {top: page}

            # And now recurse
            if which == "prop_hash":
                if type(v) == dict or isinstance(v, OrderedDict):
                    self.traverse(v, top, page)
                elif type(v) == list:
                    for x in v:
                        if type(v) == dict or isinstance(v, OrderedDict):
                            self.traverse(x, top, page)        


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
        if uri.startswith('http://vocab.getty.edu/'):
            uri = uri.replace('http://vocab.getty.edu/', '')
            uri = uri.replace('/', '&colon;')
        elif uri.startswith('https://linked.art/example/'):
            uri = uri.replace('https://linked.art/example/', '')
            uri = uri.replace('/', '')
        elif uri.startswith('http://qudt.org/1.1/vocab/unit/'):
            uri = uri.replace('http://qudt.org/1.1/vocab/unit/', 'qudt:')
        else:
            print("Unhandled URI: %s" % uri)
        return uri

    def walk(self, js, curr_int, id_map, mermaid):
        if isinstance(js, dict) or isinstance(js, OrderedDict):
            # Resource
            if 'id' in js:
                curr = js['id']
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
            t = js.get('type', '')
            if t:
                style = self.class_styles.get(t, '')
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
            for k,v in js.items():
                n += 1
                if k in ["@context", "id", "type"]:
                    continue
                elif isinstance(v, list):
                    for vi in v:
                        if isinstance(vi, dict) or isinstance(vi, OrderedDict):
                            (rng, curr_int, id_map) = self.walk(vi, curr_int, id_map, mermaid)
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
                        v = "\"''%s''\""% v
                    line = "%s-- %s -->%s_%s(%s)" % (currid, k, currid, n, v)
                    if not line in mermaid:
                        mermaid.append(line)
                        mermaid.append("class %s_%s literal;" % (currid, n))
            return (currid, curr_int, id_map)

    def on_page_markdown(self, markdown, page, config, files):

        # Do linked art extension here
        matcher = re.compile("^(```\s*crom\s*$(.+?)^```)$", re.M | re.U | re.S)
        hits = matcher.findall(markdown)
        for h in hits:
            eg = self.generate_example(h[1], page)
            markdown = markdown.replace(h[0], eg)
        return markdown



    #def on_serve(self, server, config, builder):
    #    return server


    #def on_files(self, files, config):
    #    return files

    #def on_nav(self, nav, config, files):
    #    return nav

    #def on_env(self, env, config, files):
    #    return env
    
    #def on_config(self, config):
    #    return config

    #def on_pre_template(self, template, template_name, config):
    #    return template

    #def on_template_context(self, context, template_name, config):
    #    return context
    
    #def on_post_template(self, output_content, template_name, config):
    #    return output_content
    
    #def on_pre_page(self, page, config, files):
    #    return page

    #def on_page_read_source(self, page, config):
    #    return ""

    #def on_page_content(self, html, page, config, files):
    #    return html

    #def on_page_context(self, context, page, config, nav):
    #    return context

    #def on_post_page(self, output_content, page, config):
    #    return output_content


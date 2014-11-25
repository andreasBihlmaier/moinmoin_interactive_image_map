"""

  Syntax:

  {{{#!InteractiveImageMap
  picsrc;;width=WIDTH
  area1;;shape=rect|circle|poly;;coords=V1,V2,...,Vn;;tooltip=TOOLTIP[;;description=DESCRIPTION]
  area2;;shape=rect|circle|poly;;coords=V1,V2,...,Vn;;tooltip=TOOLTIP[;;description=DESCRIPTION]
  }}}

  DESCRIPTION may contain wiki markup.

  Partly based on ImageMap Parser (http://moinmo.in/ParserMarket/ImageMap)

  @copyright: 2014 by Andreas Bihlmaier
"""

from __future__ import print_function

import re
import os
import StringIO

from MoinMoin import wikiutil, config
from MoinMoin.parser._ParserBase import ParserBase
from MoinMoin.action import AttachFile

from MoinMoin.parser import text_moin_wiki
from MoinMoin.web.request import TestRequest
from MoinMoin.web.contexts import ScriptContext


Dependencies = []


def _is_URL(text):
    return '://' in text



class Parser(ParserBase):

  parsername = "InteractiveImageMap"
  Dependencies = []

  def __init__(self, raw, request, **kw):
    self.raw = raw
    self.request = request
    print(type(request))


  def fail(self, formatter, msg):
    output_msg = "%s ERROR: %s" % (self.parsername, msg)
    try:
      self.request.write(formatter.rawHTML(output_msg))
    except:
      self.request.write(formatter.escapedText(output_msg))


  def line2dict(self, line):
    d = {}
    splitters = line.split(';;')
    d['name'] = wikiutil.escape(splitters[0])
    for splitter in splitters[1:]:
      keyval = splitter.split('=')
      if len(keyval) != 2:
        return {}
      key, val = keyval[0], keyval[1]
      d[wikiutil.escape(key)] = wikiutil.escape(val)
    return d


  def parse_wiki_markup(self, formatter, text):
    unescaped_text = text.replace('&lt;&lt;BR&gt;&gt;', '<<BR>>')
    request = ScriptContext()
    buf = StringIO.StringIO()
    request.redirect(buf)
    wiki_parser = text_moin_wiki.Parser(unescaped_text, request)
    wiki_parser.format(formatter)
    return buf.getvalue().replace('\n', ' ')


  def format(self, formatter):
    print("request:\n%s" % self.request)
    print("raw:\n%s" % self.raw)

    html = '''
<script src="http://cdn.jsdelivr.net/jquery/1.11.1/jquery.min.js"></script>
<script src="http://andreasbihlmaier.github.io/js/jquery.imagemapster.min.js"></script>
    '''

    lines = self.raw.split('\n')
    if len(lines) < 2:
      return self.fail(formatter, 'Either picsrc or area line is missing')

    image_dict = self.line2dict(lines[0])
    print("image_dict:\n%s" % image_dict)
    if not 'name' in image_dict:
      return self.fail(formatter, 'picsrc line is malformed')
    image_name = image_dict['name']
    image_dict.pop('name')

    if _is_URL(image_name):
      imgurl = image_name
    else:
      pagename, attname = AttachFile.absoluteName(image_name, formatter.page.page_name)
      imgurl = AttachFile.getAttachUrl(pagename, attname, self.request)
      attachment_fname = AttachFile.getFilename(self.request, pagename, attname)

      if not os.path.exists(attachment_fname):
        return self.fail(formatter, '%s not attached to this page' % image_name)

    image_id = re.sub(r'\W+', '', image_name)
    html += '<img id="%s" src="%s"' % (image_id, imgurl)

    if not 'width' in image_dict:
      return self.fail(formatter, 'width missing from picsrc line')
    image_width = image_dict['width']
    image_dict.pop('width')
    html += ' width=%s' % image_width

    # if required, add other image attributes here

    if image_dict:
      return self.fail(formatter, 'picsrc contains excess arguments')
    
    map_name = image_id
    html += ' usemap="#%s">' % map_name

    html += '<map name="%s">' % map_name

    areas = {}
    for line in lines[1:]:
      line_dict = self.line2dict(line)
      print("line_dict:\n%s" % line_dict)
      if not 'name' in line_dict:
        return self.fail(formatter, 'area line is malformed')
      area_name = line_dict['name']
      areas[area_name] = {'name': area_name}
      for attr in 'shape', 'coords', 'tooltip', 'description':
        if not attr in line_dict:
          return self.fail(formatter, '%s missing from %s line' % (attr, area_name))
        areas[area_name][attr] = line_dict[attr]
      areas[area_name]['description'] = self.parse_wiki_markup(formatter, line_dict['description'])
    print("areas:\n%s" % areas)

    for area in areas:
      html += '<area shape="%(shape)s" coords="%(coords)s" target="%(name)s" href="#" />' % areas[area]

    html += '</map>'


    html += '''
<div style="text-align: left; clear: both; width: %spx; height: 200px; border: 1px solid black;" id="description"></div>
</div>
   ''' % image_width

    tooltip_map_str = ''
    description_map_str = ''
    areas_str = ''
    for area in areas:
      tooltip_map_str += "%(name)s: '%(tooltip)s'," % areas[area]
      description_map_str += "%(name)s: '%(description)s'," % areas[area]
      areas_str += '{key: "%(name)s", toolTip: tooltip_map["%(name)s"]},' % areas[area]
    html += '''
<script type="text/javascript">
var default_description = 'Explore image by mouseover. Click on highlighted part in order to get more information.';
$('#description').html(default_description);

var tooltip_map = {
  %(tooltip_map)s
};
var description_map = {
  %(description_map)s
};

var image = $('#%(image_id)s');

image.mapster(
{
  fillOpacity: 0.2,
  fillColor: "00ff00",
  stroke: true,
  strokeColor: "000000",
  strokeOpacity: 0.8,
  strokeWidth: 4,
  singleSelect: true,
  mapKey: 'target',
  listKey: 'target',
  //onMouseover: function (e) {
  onClick: function (e) {
    if (!e.selected) {
      $('#description').html(default_description);
    } else {
      $('#description').html(description_map[e.key]);
    }
  },
  showToolTip: true,
  //toolTipClose: ["tooltip-click", "area-click"],
  areas: [
    %(areas)s
    ]
});
</script>
    ''' % {'tooltip_map': tooltip_map_str,
           'description_map': description_map_str,
           'image_id': image_id,
           'areas': areas_str}


    # If current formatter is a HTML formatter, output image map with formatter.rawHTML().
    # Otherwise just output image with formatter.image()
    try:
      self.request.write(formatter.rawHTML(html))
    except:
      self.request.write(formatter.image(TODO))

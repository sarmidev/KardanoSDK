#!/usr/bin/env ruby
# frozen_string_literal: true

# Structural YAML walker (Ruby stdlib Psych only; no gems).
# Prints a JSON array of every mapping key named "uses" (whitespace around
# the key is ignored) and its scalar value, including flow mappings.
# Line numbers are 1-based. Invalid YAML exits 1.
#
# Usage:
#   ruby scripts/yaml_uses_extract.rb <file>
#   ruby scripts/yaml_uses_extract.rb < file.yml

require "json"
require "psych"

def walk(node, uses)
  case node
  when Psych::Nodes::Mapping
    children = node.children || []
    i = 0
    while i + 1 < children.length
      key = children[i]
      val = children[i + 1]
      if key.is_a?(Psych::Nodes::Scalar) && key.value.to_s.strip == "uses"
        if val.is_a?(Psych::Nodes::Scalar)
          uses << {
            "line" => val.start_line + 1,
            "value" => val.value.to_s,
          }
        else
          uses << {
            "line" => (val.start_line || key.start_line) + 1,
            "value" => nil,
            "error" => "uses value is not a scalar",
          }
        end
      end
      walk(key, uses)
      walk(val, uses)
      i += 2
    end
  when Psych::Nodes::Sequence, Psych::Nodes::Document, Psych::Nodes::Stream
    (node.children || []).each { |child| walk(child, uses) }
  end
end

def top_level_keys(root)
  document = (root.children || []).find { |child| child.is_a?(Psych::Nodes::Document) } || root
  mapping = (document.children || []).find { |child| child.is_a?(Psych::Nodes::Mapping) }
  return [] if mapping.nil?

  keys = []
  children = mapping.children || []
  i = 0
  while i < children.length
    key = children[i]
    keys << key.value.to_s if key.is_a?(Psych::Nodes::Scalar)
    i += 2
  end
  keys
end

source = ARGV[0]
text = source.nil? ? $stdin.read : File.read(source)
begin
  parser = Psych::Parser.new(Psych::TreeBuilder.new)
  parser.parse(text)
rescue Psych::SyntaxError => error
  warn error.message
  exit 1
end
uses = []
walk(parser.handler.root, uses)
puts JSON.generate(
  "uses" => uses,
  "top_level_keys" => top_level_keys(parser.handler.root),
)

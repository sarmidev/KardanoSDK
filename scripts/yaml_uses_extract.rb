#!/usr/bin/env ruby
# frozen_string_literal: true

# Structural YAML walker (Ruby stdlib Psych only; no gems).
# Emits JSON with every mapping key named "uses", top-level keys, and
# the top-level `runs.using` / `runs.image` scalars (action metadata).
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

def mapping_pairs(node)
  return [] unless node.is_a?(Psych::Nodes::Mapping)

  pairs = []
  children = node.children || []
  i = 0
  while i + 1 < children.length
    pairs << [children[i], children[i + 1]]
    i += 2
  end
  pairs
end

def top_level_mapping(root)
  document = (root.children || []).find { |child| child.is_a?(Psych::Nodes::Document) } || root
  (document.children || []).find { |child| child.is_a?(Psych::Nodes::Mapping) }
end

def top_level_keys(root)
  mapping = top_level_mapping(root)
  return [] if mapping.nil?

  keys = []
  mapping_pairs(mapping).each do |key, _val|
    keys << key.value.to_s if key.is_a?(Psych::Nodes::Scalar)
  end
  keys
end

def scalar_field(node, line_fallback)
  if node.is_a?(Psych::Nodes::Scalar)
    { "line" => node.start_line + 1, "value" => node.value.to_s }
  else
    { "line" => (node.start_line || line_fallback) + 1, "value" => nil }
  end
end

def extract_runs(root)
  mapping = top_level_mapping(root)
  return {} if mapping.nil?

  runs_node = nil
  mapping_pairs(mapping).each do |key, val|
    next unless key.is_a?(Psych::Nodes::Scalar) && key.value.to_s.strip == "runs"

    runs_node = val
  end
  return {} unless runs_node.is_a?(Psych::Nodes::Mapping)

  out = {}
  mapping_pairs(runs_node).each do |key, val|
    next unless key.is_a?(Psych::Nodes::Scalar)

    name = key.value.to_s.strip
    next unless %w[using image].include?(name)

    out[name] = scalar_field(val, key.start_line)
  end
  out
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
  "runs" => extract_runs(parser.handler.root),
)

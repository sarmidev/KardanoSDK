#!/usr/bin/env ruby
# frozen_string_literal: true

# Structural YAML walker (Ruby stdlib Psych only; no gems).
# Emits JSON with every mapping key named "uses", top-level keys, and
# the top-level `runs.using` / `runs.image` scalars (action metadata).
# Line numbers are 1-based. Invalid YAML, aliases/anchors, and
# non-string uses/runs fields exit 1 with an explicit error.
#
# Usage:
#   ruby scripts/yaml_uses_extract.rb [--action-metadata] <file>
#   ruby scripts/yaml_uses_extract.rb [--action-metadata] < file.yml

require "json"
require "psych"

NULLISH = ["", "~", "null", "Null", "NULL"].freeze

def line_of(node, fallback = 0)
  raw = node.respond_to?(:start_line) ? node.start_line : nil
  (raw.nil? ? fallback : raw) + 1
end

def each_node(node, &block)
  return if node.nil?

  yield node
  return unless node.respond_to?(:children)

  (node.children || []).each { |child| each_node(child, &block) }
end

def nonempty_string_scalar?(node)
  return false unless node.is_a?(Psych::Nodes::Scalar)
  return false if node.tag.to_s.end_with?(":null")

  !NULLISH.include?(node.value.to_s.strip)
end

def collect_anchor_errors(root)
  errors = []
  each_node(root) do |node|
    if node.is_a?(Psych::Nodes::Alias)
      errors << {
        "line" => line_of(node),
        "message" => "YAML aliases are not allowed (*#{node.anchor})",
      }
      next
    end
    next unless node.respond_to?(:anchor) && !node.anchor.to_s.empty?

    errors << {
      "line" => line_of(node),
      "message" => "YAML anchors are not allowed (&#{node.anchor})",
    }
  end
  errors
end

def walk(node, uses, errors)
  case node
  when Psych::Nodes::Mapping
    children = node.children || []
    i = 0
    while i + 1 < children.length
      key = children[i]
      val = children[i + 1]
      if key.is_a?(Psych::Nodes::Scalar) && key.value.to_s.strip == "uses"
        uses.concat(uses_entries(key, val, errors))
      end
      walk(key, uses, errors)
      walk(val, uses, errors)
      i += 2
    end
  when Psych::Nodes::Sequence, Psych::Nodes::Document, Psych::Nodes::Stream
    (node.children || []).each { |child| walk(child, uses, errors) }
  end
end

def uses_entries(key, val, errors)
  line = line_of(val, key.start_line)
  if val.is_a?(Psych::Nodes::Alias)
    message = "uses value is an alias"
    errors << { "line" => line, "message" => message }
    return [{ "line" => line, "value" => nil, "error" => message }]
  end
  unless val.is_a?(Psych::Nodes::Scalar)
    message = "uses value is not a string"
    errors << { "line" => line, "message" => message }
    return [{ "line" => line, "value" => nil, "error" => message }]
  end
  unless nonempty_string_scalar?(val)
    message = "uses value is empty"
    errors << { "line" => line, "message" => message }
    return [{ "line" => line, "value" => nil, "error" => message }]
  end
  [{ "line" => line, "value" => val.value.to_s }]
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

def field_entry(node, line_fallback, errors, label, require_string:)
  line = line_of(node, line_fallback)
  if node.is_a?(Psych::Nodes::Alias)
    message = "#{label} is an alias"
    errors << { "line" => line, "message" => message }
    return { "line" => line, "value" => nil, "error" => message }
  end
  unless node.is_a?(Psych::Nodes::Scalar)
    message = "#{label} is not a string"
    errors << { "line" => line, "message" => message } if require_string
    return { "line" => line, "value" => nil, "error" => message }
  end
  unless nonempty_string_scalar?(node)
    message = "#{label} is empty"
    errors << { "line" => line, "message" => message } if require_string
    return { "line" => line, "value" => nil, "error" => message }
  end
  { "line" => line, "value" => node.value.to_s }
end

def extract_runs(root, action_metadata:, errors:)
  mapping = top_level_mapping(root)
  if mapping.nil?
    if action_metadata
      errors << { "line" => 1, "message" => "runs is missing" }
    end
    return {}
  end

  runs_key = nil
  runs_node = nil
  mapping_pairs(mapping).each do |key, val|
    next unless key.is_a?(Psych::Nodes::Scalar) && key.value.to_s.strip == "runs"

    runs_key = key
    runs_node = val
  end

  if runs_node.nil?
    if action_metadata
      errors << { "line" => 1, "message" => "runs is missing" }
    end
    return {}
  end

  unless runs_node.is_a?(Psych::Nodes::Mapping)
    line = line_of(runs_node, runs_key && runs_key.start_line)
    message = "runs is not a mapping"
    errors << { "line" => line, "message" => message }
    return { "error" => message, "line" => line }
  end

  out = {}
  mapping_pairs(runs_node).each do |key, val|
    next unless key.is_a?(Psych::Nodes::Scalar)

    name = key.value.to_s.strip
    next unless %w[using image].include?(name)

    out[name] = field_entry(
      val,
      key.start_line,
      errors,
      "runs.#{name}",
      require_string: action_metadata,
    )
  end

  if action_metadata
    using_entry = out["using"]
    if using_entry.nil?
      errors << { "line" => line_of(runs_node), "message" => "runs.using is missing or not a string" }
    end
    using_value = using_entry && using_entry["value"]
    if !using_value.to_s.strip.empty? && using_value.to_s.strip.downcase == "docker"
      image_entry = out["image"]
      image_ok = image_entry.is_a?(Hash) && image_entry["error"].nil? &&
        !image_entry["value"].to_s.strip.empty?
      unless image_ok
        line = image_entry && image_entry["line"] || line_of(runs_node)
        unless errors.any? { |item| item["message"].to_s.start_with?("runs.image") }
          errors << { "line" => line, "message" => "runs.image is missing or not a string" }
        end
      end
    end
  end
  out
end

action_metadata = false
args = ARGV.dup
action_metadata = true if args.delete("--action-metadata")
source = args[0]
text = source.nil? ? $stdin.read : File.read(source)
begin
  parser = Psych::Parser.new(Psych::TreeBuilder.new)
  parser.parse(text)
rescue Psych::SyntaxError => error
  warn error.message
  exit 1
end

root = parser.handler.root
errors = collect_anchor_errors(root)
uses = []
walk(root, uses, errors)
runs = extract_runs(root, action_metadata: action_metadata, errors: errors)

if errors.any?
  errors.each do |item|
    warn "#{item['line']}: #{item['message']}"
  end
  exit 1
end

puts JSON.generate(
  "uses" => uses,
  "top_level_keys" => top_level_keys(root),
  "runs" => runs,
  "errors" => [],
)

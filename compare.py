import re
import sys

def parse_netlist(file_path):
    """Parse a KiCad netlist file and return a dictionary with net names as keys, and a tuple (net code, node details) as values."""
    connections = {}
    net_codes = {}
    
    try:
        with open(file_path, 'r') as file:
            lines = file.readlines()
        
        net_name = None
        net_code = None
        in_nets_section = False
        
        for line in lines:
            line = line.strip()  # Remove leading/trailing whitespace
            
            if line.startswith('(nets'):
                in_nets_section = True
                continue
            elif line.startswith('(components'):
                in_nets_section = False
                continue
            
            if in_nets_section and line.startswith('(net'):
                net_match = re.match(r'\(net \(code "(\d+)"\) \(name "(.*?)"\)', line)
                if net_match:
                    net_code = net_match.group(1)
                    net_name = net_match.group(2)
                    connections[net_name] = {'code': net_code, 'nodes': []}
                    net_codes[net_name] = net_code
                    continue
            
            if in_nets_section and line.startswith('(node'):
                if net_name:
                    # Extract only up to the pin detail
                    node_detail = re.match(r'\(node \(ref "(.*?)"\) \(pin "(.*?)"\)', line)
                    if node_detail:
                        ref = node_detail.group(1)
                        pin = node_detail.group(2)
                        connections[net_name]['nodes'].append(f'(node (ref "{ref}") (pin "{pin}"))')
    
    except FileNotFoundError:
        print(f"Error: File {file_path} not found.")
    except Exception as e:
        print(f"Error: An unexpected error occurred while parsing {file_path} - {e}")
    
    return connections, net_codes


def categorize_nodes(nodes):
    """Categorize nodes into Capacitors, Resistors, and Others based on their references."""
    categories = {'Capacitors': 0, 'Resistors': 0, 'Others': 0}
    
    for node in nodes:
        ref = re.search(r'\(ref "(.*?)"\)', node)
        if ref:
            ref = ref.group(1)
            if ref.startswith('C'):
                categories['Capacitors'] += 1
            elif ref.startswith('R'):
                categories['Resistors'] += 1
            else:
                categories['Others'] += 1
    
    return categories


def generate_html_report(results, detailed_mismatches, matched_count, mismatched_count):
    """Generate the HTML report from the given results and detailed mismatches."""
    with open('template.html', 'r') as template_file:
        template = template_file.read()
    
    rows = ""
    for i, (net_name, net_code1, count1, net_code2, count2, is_mismatch) in enumerate(results, start=1):
        row_class = 'mismatch-row' if is_mismatch else 'match-row'
        rows += f'''
            <tr class="{row_class}">
                <td>{i}</td>
                <td>{net_name}</td>
                <td>{net_code1}</td>
                <td>{count1}</td>
                <td>{net_code2}</td>
                <td>{count2}</td>
            </tr>
        '''
    
    detailed_rows = ""
    for i, (net_name, unique_nodes1, count1, unique_nodes2, count2) in enumerate(detailed_mismatches, start=1):
        # Categorize nodes
        categories1 = categorize_nodes(unique_nodes1)
        categories2 = categorize_nodes(unique_nodes2)
        
        nodes1_str = "<br>".join(unique_nodes1)
        nodes2_str = "<br>".join(unique_nodes2)
        
        detailed_rows += f'''
            <tr>
                <td>{i}</td>
                <td>{net_name}</td>
                <td>
                    <p>Total Nodes: {count1}</p>
                    <p>Total Capacitors: {categories1['Capacitors']}</p>
                    <p>Total Resistors: {categories1['Resistors']}</p>
                    <p>Total Others: {categories1['Others']}</p>
                    <ul>
                        {"".join(f"<li>{node}</li>" for node in unique_nodes1)}
                    </ul>
                </td>
                <td>
                    <p>Total Nodes: {count2}</p>
                    <p>Total Capacitors: {categories2['Capacitors']}</p>
                    <p>Total Resistors: {categories2['Resistors']}</p>
                    <p>Total Others: {categories2['Others']}</p>
                    <ul>
                        {"".join(f"<li>{node}</li>" for node in unique_nodes2)}
                    </ul>
                </td>
            </tr>
        '''
    
    # Insert counts for matched and mismatched net codes
    footer_info = f'''
        <tr>
            <td colspan="6">
                <p><strong>Matched Net Codes: {matched_count}</strong></p>
                <p><strong>Mismatched Net Codes: {mismatched_count}</strong></p>
            </td>
        </tr>
    '''
    
    html_content = template.replace('{{ rows }}', rows).replace('{{ detailed_rows }}', detailed_rows).replace('{{ footer_info }}', footer_info)
    
    with open('comparison_report.html', 'w') as html_file:
        html_file.write(html_content)
    
    print("HTML report generated as 'comparison_report.html'")


def compare_netlists(file1, file2):
    """Compare two KiCad netlist files and generate an HTML report."""
    netlist1, net_codes1 = parse_netlist(file1)
    netlist2, net_codes2 = parse_netlist(file2)
    
    all_nets = set(netlist1.keys()).union(netlist2.keys())
    
    # Collect all results with mismatches sorted first
    results = []
    detailed_mismatches = []
    matched_count = 0
    mismatched_count = 0
    
    for net_name in all_nets:
        net_code1 = net_codes1.get(net_name, 'N/A')
        net_code2 = net_codes2.get(net_name, 'N/A')
        nodes1 = netlist1.get(net_name, {'nodes': []})['nodes']
        nodes2 = netlist2.get(net_name, {'nodes': []})['nodes']
        count1 = len(nodes1)
        count2 = len(nodes2)
        
        # Find unique nodes
        unique_nodes1 = [node for node in nodes1 if node not in nodes2]
        unique_nodes2 = [node for node in nodes2 if node not in nodes1]
        
        count_unique1 = len(unique_nodes1)
        count_unique2 = len(unique_nodes2)
        is_mismatch = count_unique1 != count_unique2
        
        results.append((net_name, net_code1, count1, net_code2, count2, is_mismatch))
        
        if is_mismatch:
            detailed_mismatches.append((net_name, unique_nodes1, count_unique1, unique_nodes2, count_unique2))
            mismatched_count += 1
        else:
            matched_count += 1
    
    # Sort results: mismatches first, then matches, and within each group sort by net code
    results.sort(key=lambda x: (not x[5], x[1]))

    generate_html_report(results, detailed_mismatches, matched_count, mismatched_count)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python compare.py <file1.net> <file2.net>")
        sys.exit(1)
    
    file1 = sys.argv[1]
    file2 = sys.argv[2]
    
    compare_netlists(file1, file2)

#include <iostream>
#include <fstream>
#include <sstream>
#include <unordered_map>
#include <vector>
#include <string>

std::vector<std::string> split_csv_row(const std::string& line) {
    std::vector<std::string> result;
    std::stringstream ss(line);
    std::string cell;

    while (std::getline(ss, cell, ',')) {
        result.push_back(cell);
    }

    return result;
}

std::string make_key(const std::vector<std::string>& row,
                     size_t package_idx, size_t arch_idx, size_t release_idx) {
    return row[package_idx] + "|" + row[arch_idx] + "|" + row[release_idx];
}

int main(int argc, char* argv[]) {
    if (argc != 2) {
        std::cerr << "Usage: ./csv_hashmap <csv_file>\n";
        return 1;
    }

    std::ifstream file(argv[1]);
    if (!file) {
        std::cerr << "Error opening file: " << argv[1] << "\n";
        return 1;
    }

    std::string line;
    std::getline(file, line);
    std::vector<std::string> headers = split_csv_row(line);

    size_t package_idx = -1, arch_idx = -1, release_idx = -1;
    for (size_t i = 0; i < headers.size(); ++i) {
        if (headers[i] == "package") package_idx = i;
        if (headers[i] == "architecture") arch_idx = i;
        if (headers[i] == "release") release_idx = i;
    }

    if (package_idx == std::string::npos || arch_idx == std::string::npos || 
        release_idx == std::string::npos) {
        std::cerr << "Missing required columns (package, architecture, release)\n";
        return 1;
    }

    std::unordered_map<std::string, std::vector<std::string>> hashmap;
    size_t line_num = 1;

    while (std::getline(file, line)) {
        line_num++;
        std::vector<std::string> row = split_csv_row(line);
        if (row.size() != headers.size()) {
            std::cerr << "Warning: Skipping malformed line " << line_num << "\n";
            continue;
        }

        std::string key = make_key(row, package_idx, arch_idx, release_idx);
        hashmap[key] = row;
    }

    std::cout << "✅ Loaded " << hashmap.size() << " unique entries.\n";

    // Example lookup:
    std::string query_package = "openssl";
    std::string query_arch = "amd64";
    std::string query_release = "22.04";
    std::string query_key = query_package + "|" + query_arch + "|" + query_release;

    auto it = hashmap.find(query_key);
    if (it != hashmap.end()) {
        std::cout << "🔍 Found: ";
        for (const auto& col : it->second) std::cout << col << " | ";
        std::cout << "\n";
    } else {
        std::cout << "❌ Not found: " << query_key << "\n";
    }

    return 0;
}

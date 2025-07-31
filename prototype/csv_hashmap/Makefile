# Makefile to build the csv_hashmap program

CXX = g++
CXXFLAGS = -std=c++17 -Wall -Wextra -O2

TARGET = csv_hashmap
SRC = csv_hashmap.cpp

all: $(TARGET)

$(TARGET): $(SRC)
	$(CXX) $(CXXFLAGS) -o $(TARGET) $(SRC)

clean:
	rm -f $(TARGET)

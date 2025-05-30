#!/usr/bin/env python3

import sys
import time
import uuid
import struct
import socket
import threading
import subprocess
import requests
from contextlib import closing

def wait_for_server(host, port, timeout=10):
    """Wait for server to start accepting connections"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except (ConnectionRefusedError, OSError):
            time.sleep(0.1)
    return False

def read_fully(sock, length):
    """Read exactly length bytes from socket"""
    result = b''
    while len(result) < length:
        chunk = sock.recv(length - len(result))
        if not chunk:
            raise ConnectionError("Socket closed unexpectedly")
        result += chunk
    return result

def test_web_interface():
    """Test web interface returns 200 OK"""
    print("Testing web interface...")
    try:
        response = requests.get("http://127.0.0.1:29950/status", timeout=5)
        if response.status_code == 200:
            print("✓ Web interface test PASSED (200 OK)")
            return True
        else:
            print(f"✗ Web interface test FAILED (status {response.status_code})")
            return False
    except Exception as e:
        print(f"✗ Web interface test FAILED: {e}")
        return False

def test_newstyle_list_empty():
    """Test new-style list endpoint returns empty server list"""
    print("Testing new-style list endpoint (empty)...")
    try:
        LIST_PROTOCOL_ID = uuid.UUID("297d0df4-430c-bf61-640a-640897eaef57")
        GG2_LOBBY_ID = uuid.UUID("1ccf16b1-436d-856f-504d-cc1af306aaa7")
        
        with closing(socket.create_connection(("127.0.0.1", 29944), timeout=5)) as sock:
            # Send query for GG2 lobby
            query = LIST_PROTOCOL_ID.bytes + GG2_LOBBY_ID.bytes
            sock.sendall(query)
            
            # Read server count (should be 0)
            servercount_data = read_fully(sock, 4)
            servercount = struct.unpack('>L', servercount_data)[0]
            
            if servercount == 0:
                print("✓ New-style list test PASSED (0 servers)")
                return True
            else:
                print(f"✗ New-style list test FAILED (expected 0, got {servercount} servers)")
                return False
    except Exception as e:
        print(f"✗ New-style list test FAILED: {e}")
        return False

def test_server_registration():
    """Test registering a server via new-style protocol"""
    print("Testing server registration...")
    try:
        # Protocol UUIDs
        REG_PROTOCOL_ID = uuid.UUID("b5dae2e8-424f-9ed0-0fcb-8c21c7ca1352")
        SERVER_ID = uuid.uuid4()
        GG2_LOBBY_ID = uuid.UUID("1ccf16b1-436d-856f-504d-cc1af306aaa7")
        
        # Create registration packet
        packet = REG_PROTOCOL_ID.bytes  # Protocol ID (16 bytes)
        packet += SERVER_ID.bytes       # Server ID (16 bytes)
        packet += GG2_LOBBY_ID.bytes    # Lobby ID (16 bytes)
        packet += struct.pack(">B", 1)  # Protocol: UDP=1 (1 byte)
        packet += struct.pack(">H", 12345)  # Port (2 bytes)
        packet += struct.pack(">HHH", 8, 2, 0)  # slots, players, bots (6 bytes)
        packet += bytes([0])  # Reserved byte
        packet += struct.pack(">B", 0)  # Flags (1 byte)
        
        # Key-value pairs
        kvpairs = []
        # Add name
        name = "Test Server"
        name_bytes = name.encode('utf-8')
        kvpairs.append(bytes([4]) + b"name" + struct.pack(">H", len(name_bytes)) + name_bytes)
        
        # Add game info
        game = "Test Game"
        game_bytes = game.encode('utf-8')
        kvpairs.append(bytes([4]) + b"game" + struct.pack(">H", len(game_bytes)) + game_bytes)
        
        # Add protocol_id (binary)
        protocol_id_bytes = uuid.uuid4().bytes
        kvpairs.append(bytes([11]) + b"protocol_id" + struct.pack(">H", len(protocol_id_bytes)) + protocol_id_bytes)
        
        # Pack key-value count and data
        packet += struct.pack(">H", len(kvpairs))  # KV count (2 bytes)
        packet += b"".join(kvpairs)
        
        # Send registration
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.sendto(packet, ("127.0.0.1", 29944))
        
        # Give server time to process
        time.sleep(0.5)
        
        # Now check if server appears in list
        LIST_PROTOCOL_ID = uuid.UUID("297d0df4-430c-bf61-640a-640897eaef57")
        
        with closing(socket.create_connection(("127.0.0.1", 29944), timeout=5)) as sock:
            query = LIST_PROTOCOL_ID.bytes + GG2_LOBBY_ID.bytes
            sock.sendall(query)
            
            servercount_data = read_fully(sock, 4)
            servercount = struct.unpack('>L', servercount_data)[0]
            
            if servercount == 1:
                # Read the server data to verify it's correct
                serverlen_data = read_fully(sock, 4)
                serverlen = struct.unpack('>L', serverlen_data)[0]
                serverblock = read_fully(sock, serverlen)
                
                # Parse server data
                (protocol, ipv4_port, ipv4_ip, ipv6_port, ipv6_ip, 
                 slots, players, bots, flags, infolen) = struct.unpack(">BH4sH16sHHHHH", serverblock[:35])
                
                if slots == 8 and players == 2 and bots == 0:
                    print("✓ Server registration test PASSED (server registered and found)")
                    return True
                else:
                    print(f"✗ Server registration test FAILED (wrong server data: slots={slots}, players={players}, bots={bots})")
                    return False
            else:
                print(f"✗ Server registration test FAILED (expected 1 server, got {servercount})")
                return False
                
    except Exception as e:
        print(f"✗ Server registration test FAILED: {e}")
        return False

def test_legacy_protocol():
    """Test legacy GG2 protocol registration and query"""
    print("Testing legacy GG2 protocol...")
    
    # Choose a port for our mock server
    mock_server_port = 23456
    connection_received = threading.Event()
    
    def mock_server():
        """Mock game server that accepts the lobby's connection check"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_sock:
                server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                server_sock.bind(("127.0.0.1", mock_server_port))
                server_sock.listen(1)
                server_sock.settimeout(5.0)  # Don't wait forever
                
                try:
                    conn, _ = server_sock.accept()
                    connection_received.set()
                    conn.close()
                except socket.timeout:
                    pass  # Timeout is ok, maybe the test failed elsewhere
        except Exception:
            pass  # If port is busy, etc.
    
    try:
        # Start mock server in background
        server_thread = threading.Thread(target=mock_server, daemon=True)
        server_thread.start()
        
        # Give server time to start
        time.sleep(0.1)
        
        # Legacy magic numbers
        MAGIC_NUMBERS = bytes([4, 8, 15, 16, 23, 42])
        
        # Create legacy registration packet
        packet = MAGIC_NUMBERS
        packet += bytes([1])  # Simple version (not 128)
        packet += struct.pack("<H", mock_server_port)  # Port (little endian)
        
        # Info string
        info = "Test Legacy Server [5/10]"
        info_bytes = info.encode('utf-8')
        packet += bytes([len(info_bytes)])
        packet += info_bytes
        
        # Send registration
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.sendto(packet, ("127.0.0.1", 29942))
        
        # Wait for connection check to complete
        if not connection_received.wait(timeout=3.0):
            print("✗ Legacy protocol test FAILED (lobby didn't connect for reachability check)")
            return False
            
        # Give server time to process registration
        time.sleep(0.5)
        
        # Query using legacy protocol
        with closing(socket.create_connection(("127.0.0.1", 29942), timeout=5)) as sock:
            # Send version query
            sock.sendall(bytes([1]))  # Simple version
            
            # Read response
            response = sock.recv(1024)
            if len(response) == 0:
                print("✗ Legacy protocol test FAILED (no response)")
                return False
                
            server_count = response[0]
            if server_count == 0:
                print("✗ Legacy protocol test FAILED (no servers registered)")
                return False
                
            # Parse server data to verify it's correct
            offset = 1
            for _ in range(server_count):
                if offset >= len(response):
                    print("✗ Legacy protocol test FAILED (truncated response)")
                    return False
                    
                info_len = response[offset]
                offset += 1
                
                if offset + info_len + 6 > len(response):  # info + IP(4) + port(2)
                    print("✗ Legacy protocol test FAILED (truncated server data)")
                    return False
                    
                server_info = response[offset:offset + info_len].decode('utf-8', 'replace')
                offset += info_len
                
                # Skip IP and port
                offset += 6
                
                # Verify server info contains our test data
                if "Test Legacy Server" in server_info and "[5/10]" in server_info:
                    print(f"✓ Legacy protocol test PASSED (registered server found: {server_info})")
                    return True
                    
            print(f"✗ Legacy protocol test FAILED (server registered but with wrong info)")
            return False
                
    except Exception as e:
        print(f"✗ Legacy protocol test FAILED: {e}")
        return False

def run_tests():
    """Run all integration tests"""
    print("Starting Faucet Lobby integration tests...")
    print("=" * 50)
    
    # Start the lobby server
    print("Starting lobby server...")
    server_process = subprocess.Popen([
        sys.executable, "lobby.py"
    ], cwd="/home/simeon/Schreibtisch/Projektmaterial/upgrade-faucet-lobby/Faucet-Lobby")
    
    try:
        # Wait for server to start
        if not wait_for_server("127.0.0.1", 29942):
            print("✗ Server failed to start on port 29942")
            return False
        if not wait_for_server("127.0.0.1", 29944):
            print("✗ Server failed to start on port 29944")  
            return False
        if not wait_for_server("127.0.0.1", 29950):
            print("✗ Server failed to start on port 29950")
            return False
            
        print("✓ Server started successfully")
        print()
        
        # Run tests
        results = []
        results.append(test_web_interface())
        results.append(test_newstyle_list_empty())
        results.append(test_server_registration())
        results.append(test_legacy_protocol())
        
        print()
        print("=" * 50)
        passed = sum(results)
        total = len(results)
        print(f"Test Results: {passed}/{total} tests passed")
        
        if passed == total:
            print("🎉 All tests PASSED!")
            return True
        else:
            print("❌ Some tests FAILED!")
            return False
            
    finally:
        # Clean up
        print("\nShutting down server...")
        server_process.terminate()
        server_process.wait(timeout=5)

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
#!/usr/bin/env python3
"""
ARCHİVERR API TEST SCRIPT

Bu script API'yi interaktif olarak test etmek için kullanılır.

Kullanım:
    1. API başlat: python -m archiverr serve
    2. Bu scripti çalıştır: python test_api.py

Gerekli paketler:
    pip install httpx websockets

Test modları:
    python test_api.py              # Tüm testler
    python test_api.py health       # Sadece health check
    python test_api.py run          # Execution testi (sync)
    python test_api.py stream       # WebSocket stream testi
    python test_api.py sse          # SSE stream testi
"""

import asyncio
import json
import sys
from datetime import datetime

try:
    import httpx
except ImportError:
    print("❌ httpx not installed. Run: pip install httpx")
    sys.exit(1)

BASE_URL = "http://localhost:8000"
API_URL = f"{BASE_URL}/api/v1"

# Default client settings - follow redirects to handle 307
DEFAULT_TIMEOUT = 120.0
DEFAULT_FOLLOW_REDIRECTS = True


def print_header(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def print_json(data: dict):
    print(json.dumps(data, indent=2, ensure_ascii=False, default=str))


async def test_health():
    """Test health endpoint"""
    print_header("🏥 Health Check")
    
    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, follow_redirects=DEFAULT_FOLLOW_REDIRECTS) as client:
        try:
            r = await client.get(f"{API_URL}/system/health")
            print(f"Status: {r.status_code}")
            
            if r.status_code == 200:
                print_json(r.json())
                return True
            else:
                print(f"❌ Unexpected status code: {r.status_code}")
                print(f"   Response: {r.text[:500]}")
                return False
                
        except httpx.ConnectError:
            print("❌ API'ye bağlanılamadı! API çalışıyor mu?")
            print("   Başlatmak için: python -m archiverr serve")
            return False
        except Exception as e:
            print(f"❌ Beklenmeyen hata: {type(e).__name__}: {e}")
            return False


async def test_system_status():
    """Test system status endpoint"""
    print_header("ℹ️  System Status")
    
    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, follow_redirects=DEFAULT_FOLLOW_REDIRECTS) as client:
        try:
            r = await client.get(f"{API_URL}/system/status")
            print(f"Status: {r.status_code}")
            
            if r.status_code == 200:
                print_json(r.json())
            else:
                print(f"❌ Hata: {r.text[:500]}")
        except Exception as e:
            print(f"❌ Hata: {type(e).__name__}: {e}")


async def test_list_executions():
    """Test list executions endpoint"""
    print_header("📋 List Executions")
    
    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, follow_redirects=DEFAULT_FOLLOW_REDIRECTS) as client:
        try:
            r = await client.get(f"{API_URL}/executions")
            print(f"Status: {r.status_code}")
            
            if r.status_code == 200:
                data = r.json()
                print(f"Total: {data.get('total', 0)} executions")
                if data.get('executions'):
                    for e in data['executions'][:3]:
                        print(f"  - {e['execution_id']}: {e['status']}")
            else:
                print(f"❌ Hata: {r.text[:500]}")
        except Exception as e:
            print(f"❌ Hata: {type(e).__name__}: {e}")


async def test_list_branches():
    """Test list branches endpoint"""
    print_header("🌿 List Branches")
    
    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, follow_redirects=DEFAULT_FOLLOW_REDIRECTS) as client:
        try:
            r = await client.get(f"{API_URL}/versioning/branches")
            print(f"Status: {r.status_code}")
            
            if r.status_code == 200:
                data = r.json()
                print(f"Total: {data.get('total', 0)} branches")
                if data.get('branches'):
                    for b in data['branches']:
                        print(f"  - {b['name']}: {b.get('description', 'No description')}")
            else:
                print(f"❌ Hata: {r.text[:500]}")
        except Exception as e:
            print(f"❌ Hata: {type(e).__name__}: {e}")


async def test_run_sync():
    """Test run endpoint (synchronous)"""
    print_header("🚀 Run Execution (Sync)")
    
    print("Çalıştırılıyor... (Bu birkaç saniye sürebilir)")
    print("")
    
    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, follow_redirects=DEFAULT_FOLLOW_REDIRECTS) as client:
        try:
            r = await client.post(
                f"{API_URL}/run/",  # Note: trailing slash to avoid 307 redirect
                json={"dry_run": True, "debug": False}
            )
            print(f"Status: {r.status_code}")
            
            # Handle non-200 responses
            if r.status_code != 200:
                print(f"❌ Beklenmeyen status code: {r.status_code}")
                print(f"   Response: {r.text[:1000] if r.text else 'Empty response'}")
                return
            
            # Try to parse JSON
            try:
                data = r.json()
            except Exception as e:
                print(f"❌ JSON parse hatası: {e}")
                print(f"   Response: {r.text[:1000] if r.text else 'Empty response'}")
                return
            
            if data.get('success'):
                print(f"✅ Başarılı!")
                print(f"   Execution ID: {data.get('execution_id')}")
                print(f"   Total Matches: {data.get('total_matches')}")
                print(f"   Duration: {data.get('duration_ms')}ms")
            else:
                print(f"❌ Hata: {data.get('error')}")
            
            # Show summary if available
            if data.get('api_response'):
                api_response = data['api_response']
                globals_status = api_response.get('globals', {}).get('status', {})
                print(f"\n📊 Özet:")
                print(f"   Matches: {globals_status.get('matches', 0)}")
                print(f"   Tasks: {globals_status.get('tasks', 0)}")
                print(f"   Errors: {globals_status.get('errors', 0)}")
                
        except httpx.ConnectError:
            print("❌ API'ye bağlanılamadı!")
        except httpx.TimeoutException:
            print("❌ Zaman aşımı! Execution çok uzun sürdü.")
        except Exception as e:
            print(f"❌ Beklenmeyen hata: {type(e).__name__}: {e}")


async def test_run_async_with_sse():
    """Test async run with Server-Sent Events"""
    print_header("📡 Run with SSE Stream")
    
    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, follow_redirects=DEFAULT_FOLLOW_REDIRECTS) as client:
        try:
            # Start async execution
            r = await client.post(
                f"{API_URL}/run/async/",  # Note: trailing slash
                json={"dry_run": True, "debug": False}
            )
            
            if r.status_code != 200:
                print(f"❌ Execution başlatılamadı: {r.status_code}")
                print(f"   Response: {r.text[:500] if r.text else 'Empty'}")
                return
            
            try:
                data = r.json()
            except Exception as e:
                print(f"❌ JSON parse hatası: {e}")
                return
            
            execution_id = data.get('execution_id')
            if not execution_id:
                print(f"❌ execution_id bulunamadı: {data}")
                return
                
            print(f"✅ Execution başlatıldı: {execution_id}")
            print(f"   Stream URL: {data.get('stream_url', 'N/A')}")
            print("")
            print("📡 SSE Stream dinleniyor...")
            print("-" * 40)
            
            # Listen to SSE stream
            async with client.stream('GET', f"{API_URL}/run/{execution_id}/events") as response:
                async for line in response.aiter_lines():
                    if line.startswith('data:'):
                        try:
                            event_data = json.loads(line[5:].strip())
                        except json.JSONDecodeError:
                            continue
                        
                        if event_data.get('type') == 'keepalive':
                            continue
                        
                        status = event_data.get('status', '')
                        message = event_data.get('message', '')
                        percent = event_data.get('percent', 0)
                        
                        print(f"[{percent:5.1f}%] {status}: {message}")
                        
                        if status in ['done', 'completed', 'failed']:
                            break
            
            print("-" * 40)
            print("✅ Stream tamamlandı")
            
        except httpx.ConnectError:
            print("❌ API'ye bağlanılamadı!")
        except Exception as e:
            print(f"❌ Beklenmeyen hata: {type(e).__name__}: {e}")


async def test_run_with_websocket():
    """Test async run with WebSocket"""
    print_header("🔌 Run with WebSocket Stream")
    
    try:
        import websockets
    except ImportError:
        print("❌ websockets not installed. Run: pip install websockets")
        return
    
    execution_id = None
    
    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, follow_redirects=DEFAULT_FOLLOW_REDIRECTS) as client:
        try:
            # Start async execution
            r = await client.post(
                f"{API_URL}/run/async/",  # Note: trailing slash
                json={"dry_run": True, "debug": False}
            )
            
            if r.status_code != 200:
                print(f"❌ Execution başlatılamadı: {r.status_code}")
                print(f"   Response: {r.text[:500] if r.text else 'Empty'}")
                return
            
            try:
                data = r.json()
            except Exception as e:
                print(f"❌ JSON parse hatası: {e}")
                return
            
            execution_id = data.get('execution_id')
            if not execution_id:
                print(f"❌ execution_id bulunamadı: {data}")
                return
                
            print(f"✅ Execution başlatıldı: {execution_id}")
            print("")
            print("🔌 WebSocket bağlantısı kuruluyor...")
            print("-" * 40)
            
        except Exception as e:
            print(f"❌ Execution başlatma hatası: {type(e).__name__}: {e}")
            return
    
    if not execution_id:
        return
    
    # Connect to WebSocket
    ws_url = f"ws://localhost:8000/api/v1/run/{execution_id}/stream"
    
    try:
        async with websockets.connect(ws_url) as ws:
            async for msg in ws:
                try:
                    event_data = json.loads(msg)
                except json.JSONDecodeError:
                    continue
                
                if event_data.get('type') == 'keepalive':
                    continue
                
                if event_data.get('error'):
                    print(f"❌ Hata: {event_data['error']}")
                    break
                
                status = event_data.get('status', '')
                message = event_data.get('message', '')
                percent = event_data.get('percent', 0)
                
                print(f"[{percent:5.1f}%] {status}: {message}")
                
                if status in ['done', 'completed', 'failed']:
                    break
    except Exception as e:
        print(f"❌ WebSocket hatası: {type(e).__name__}: {e}")
    
    print("-" * 40)
    print("✅ Stream tamamlandı")


async def main():
    """Main test runner"""
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    
    print_header("ARCHİVERR API TEST")
    print(f"Base URL: {BASE_URL}")
    print(f"Mode: {mode}")
    
    # First check if API is running
    if not await test_health():
        return
    
    if mode == "health":
        return
    
    if mode == "all":
        await test_system_status()
        await test_list_executions()
        await test_list_branches()
        await test_run_sync()
    elif mode == "run":
        await test_run_sync()
    elif mode == "stream":
        await test_run_async_with_sse()
    elif mode == "ws":
        await test_run_with_websocket()
    elif mode == "status":
        await test_system_status()
    elif mode == "executions":
        await test_list_executions()
    elif mode == "branches":
        await test_list_branches()
    else:
        print(f"Bilinmeyen mod: {mode}")
        print("Kullanılabilir modlar: all, health, info, executions, branches, run, stream, ws")


if __name__ == "__main__":
    asyncio.run(main())

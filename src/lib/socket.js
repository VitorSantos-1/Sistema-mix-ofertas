import { io } from 'socket.io-client'

// Socket.IO servido pelo backend (python-socketio) no mesmo host, path /socket.io.
let socket = null

export function getSocket() {
  if (!socket) {
    socket = io({
      path: '/socket.io',
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionDelay: 800,
    })
  }
  return socket
}

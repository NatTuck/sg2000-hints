
# Setup Steps

- Write fishwaldo image to SD (the *duos* image)
- ssh-copy-id for passwordless ssh
- sudo visudo: `%sudo   ALL=(ALL:ALL) NOPASSWD: ALL`
- That's sufficient for a local opencode to hack up the board.

Once the board is reachable, see [`fishwaldo-arduino.md`](fishwaldo-arduino.md)
for building and running Arduino sketches on the second core.

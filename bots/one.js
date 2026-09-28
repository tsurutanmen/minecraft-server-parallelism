// join as <name>, tp to (x,z), stay until killed
const mineflayer = require('mineflayer')
const [name, x, z] = [process.argv[2], +process.argv[3], +process.argv[4]]
const bot = mineflayer.createBot({ host: '127.0.0.1', port: 25565, username: name, version: '26.1', auth: 'offline' })
bot.once('spawn', async () => {
  const w = (ms) => new Promise((r) => setTimeout(r, ms))
  await w(1500); bot.chat('/gamemode creative @s'); await w(500); bot.chat(`/tp @s ${x} 200 ${z}`)
  await w(8000); console.log('POS', name, bot.entity.position.toString())
})
bot.on('kicked', (r) => console.log('KICKED', name, r)); bot.on('error', (e) => console.log('ERR', e.message))

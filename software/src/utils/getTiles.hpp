#ifndef GET_TILES_HPP
#define GET_TILES_HPP

#include <trainingTypes.h>
/**
 * Converts pixel coordinates to tile coordinates for U8G2 display
 *
 * Display: 128x64 pixels divided into 8x8 tiles
 * Pixel space: (0,0) at top-left, (128,64) at bottom-right
 * Tile space: (0,0) at bottom-right, (16,8) at top-left
 *
 * @param px_x X coordinate in pixels (0-127)
 * @param px_y Y coordinate in pixels (0-63)
 * @param px_w Width in pixels
 * @param px_h Height in pixels
 * @param tiles Output array of 4 integers: [tile_x, tile_y, tile_w, tile_h]
 * @param lastTiles Previous tile coordinates for optimization
 */
inline void getTiles(const int px_x, const int px_y, const int px_w,
                     const int px_h, int (&tiles)[4], int (&lastTiles)[4]) {
    tiles[0] = constrain(
        floor((128.0f - static_cast<float>(px_x + px_w)) / 8.0f), 0, 15);
    tiles[1] = constrain(
        floor((64.0f - static_cast<float>(px_y + px_h)) / 8.0f), 0, 7);
    tiles[2] = constrain(ceil((static_cast<float>(px_w + px_x % 8)) / 8.0f), 1,
                         16 - tiles[0]);
    tiles[3] = constrain(ceil(static_cast<float>(px_h + px_y % 8) / 8.0f), 1,
                         8 - tiles[1]);

    const int newTiles[4] = {tiles[0], tiles[1], tiles[2], tiles[3]};

    if (tiles[0] < lastTiles[0]) {
        tiles[2] = constrain(lastTiles[2] + abs(lastTiles[0] - tiles[0]) + 1, 1,
                             16 - tiles[0]);
    } else if (tiles[0] > lastTiles[0]) {
        tiles[0] = lastTiles[0];
        tiles[2] = constrain(tiles[2] + abs(lastTiles[0] - tiles[0]) + 1, 1,
                             16 - tiles[0]);
    } else {
        tiles[2] = max(lastTiles[2], tiles[2]);
    }

    lastTiles[0] = newTiles[0];
    lastTiles[1] = newTiles[1];
    lastTiles[2] = newTiles[2];
    lastTiles[3] = newTiles[3];
}

#endif  // GET_TILES_HPP

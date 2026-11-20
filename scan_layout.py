"""Pure coordinate-free shard-list navigation math."""
def row_for_index(index,visible_rows):
    if index<0 or visible_rows<2:raise ValueError('Invalid index/visible rows')
    return min(index,visible_rows-1),max(0,index-(visible_rows-1))

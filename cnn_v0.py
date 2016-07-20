import os
from theano import tensor as T
import utils as u
from matplotlib import pyplot as plt
import nets
import dataset_utils as du
import numpy as np
from theano.sandbox import cuda as c
c.use('gpu0')


def run_cnn_v0():
    # network params
    save_net_b = True
    load_net_b = False

    # data params
    label_path = './data/volumes/labels_a.h5'
    raw_path = './data/volumes/membranes_a.h5'
    net_name = 'cnn_v0_test'
    save_net_path = './data/nets/' + net_name + '/'
    load_net_path = './data/nets/cnn_v0/net_10000'
    tmp_path = '/media/liory/ladata/bla'
    batch_size = 32
    patch_len = 40
    global_edge_len = 100

    # initialize the net
    print 'initializing network graph'
    target_t = T.ftensor4()
    l_in, l_out = nets.build_net_v0()

    print 'compiling theano functions'
    loss_train_f, loss_valid_f, probs_f = \
        nets.loss_updates_probs_v0(l_in, target_t, l_out)

    print 'Loading data and Priority queue init'
    bm = du.BatchManV0(raw_path, label_path, batch_size=batch_size,
                       patch_len=patch_len, global_edge_len=global_edge_len)
    bm.init_train_batch()
    bm_val = du.BatchManV0(raw_path, label_path, batch_size=batch_size,
                           patch_len=patch_len, global_edge_len=global_edge_len)

    bm_val.init_train_batch()  # Training

    # init a network folder where all images, models and hyper params are stored
    if save_net_b:
        if not os.path.exists(save_net_path):
            os.mkdir(save_net_path)
            os.mkdir(save_net_path + '/images')

    if load_net_b:
        u.load_network(load_net_path, l_out)

    converged = False
    max_iter = 10000000
    iteration = -1
    global_field_change = 100
    global_field_counter = 0
    save_counter = 10000     # save every n iterations
    losses = [[], [], []]
    iterations = []

    while not converged and (iteration < max_iter):
        iteration += 1
        global_field_counter += 1

        # save image and update global field ground
        if global_field_counter % global_field_change == 0:
            if save_net_b:
                # plot train images
                u.save_3_images(
                    bm.global_claims[4, bm.pad:-bm.pad-1, bm.pad:-bm.pad-1],
                    bm.global_batch[4, 0, bm.pad:-bm.pad-1, bm.pad:-bm.pad-1],
                    bm.global_label_batch[4, 0, bm.pad:-bm.pad-1, bm.pad:-bm.pad-1],
                    save_net_path + '/images/',
                    iterations_per_image=global_field_counter, name='train',
                    iteration=iteration)
                # # # plot valid images
                u.save_3_images(
                    bm_val.global_claims[4, bm_val.pad:-bm_val.pad - 1,
                                         bm_val.pad:-bm_val.pad - 1],
                    bm_val.global_batch[4, 0, bm_val.pad:-bm_val    .pad - 1,
                                        bm_val.pad:-bm_val.pad - 1],
                    bm_val.global_label_batch[4, 0, bm.pad:-bm.pad-1, bm.pad:-bm.pad-1],
                    save_net_path + '/images/',
                    iterations_per_image=global_field_counter, name='valid',
                    iteration=iteration)
                global_field_change = \
                    u.linear_growth(iteration,
                                    maximum=(global_edge_len - patch_len)**2-100,
                                    y_intercept=20, iterations_to_max=10000)

                # print '\n global field change', global_field_change

            print '\r new global batch loaded', global_field_counter, \
                global_field_change,
            bm.init_train_batch()
            bm_val.init_train_batch()
            global_field_counter = 0

        if iteration % save_counter == 0 and save_net_b:
            u.save_network(save_net_path, l_out, 'net_%i' % iteration)

        # train da thing
        raw, gt, seeds, ids = bm.get_batches()
        probs = probs_f(raw)
        if iteration % 10 == 0:
            loss_train = float(loss_train_f(raw, gt))
        bm.update_priority_queue(probs, seeds, ids)

        # monitor growing on validation set
        raw_val, gt_val, seeds_val, ids_val = bm_val.get_batches()
        probs_val = probs_f(raw_val)
        bm_val.update_priority_queue(probs_val, seeds_val, ids_val)

        if iteration % 100 == 0:
            loss_valid = float(loss_valid_f(raw_val, gt_val))
            loss_train_no_reg = float(loss_valid_f(raw, gt))
            print '\r loss train %.4f, loss train_noreg %.4f, ' \
                  'loss_validation %.4f, iteration %i' % \
                  (loss_train, loss_train_no_reg, loss_valid, iteration),

            iterations.append(iteration)
            losses[0].append(loss_train)
            losses[1].append(loss_train_no_reg)
            losses[2].append(loss_valid)
            u.plot_train_val_errors(losses,
                                    iterations,
                                    save_net_path + 'training.png',
                                    names=['loss train', 'loss train no reg',
                                           'loss valid'])

            # debug
            # f, ax = plt.subplots(1, 3)
            # ax[0].imshow(bm.global_claims[4, bm.pad:-bm.pad, bm.pad:-bm.pad],
            #              interpolation='none', cmap=u.random_color_map())
            # ax[1].imshow(bm.global_batch[4, 0, bm.pad:-bm.pad, bm.pad:-bm.pad],
            #              cmap='gray')
            # print bm.global_label_batch.shape
            # ax[2].imshow(bm.global_label_batch[4, 0, bm.pad:-bm.pad, bm.pad:-bm.pad],
            #              interpolation='none', cmap=u.random_color_map())
            #
            # print 'gt', gt[4]
            # plt.savefig(tmp_path)
            # plt.close()
            #
            #
            # f, ax = plt.subplots(1, 3)
            # ax[0].imshow(raw[4, 0], cmap='gray')
            # ax[1].imshow(raw[4, 1], cmap=u.random_color_map(),
            #              interpolation='none')
            # ax[2].imshow(gt[4, :, :, 0], cmap=u.random_color_map(),
            #              interpolation='none')
            # plt.savefig(tmp_path + str(2))
            # plt.close()


if __name__ == '__main__':

    run_cnn_v0()














